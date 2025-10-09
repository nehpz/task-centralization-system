#!/usr/bin/env -S uv run --quiet python
"""
Weekly Validation Report

Validates that all Granola meetings from the past week have been captured in Obsidian.
Generates a comprehensive weekly report with coverage statistics.

Run this weekly (Sunday 10 AM) via cron.
"""

import json
import logging
import sys
from datetime import datetime, timedelta
from pathlib import Path

# Add src to path
sys.path.insert(0, str(Path(__file__).parent.parent / "src"))

from credential_manager import CredentialManager

logger = logging.getLogger(__name__)


class WeeklyValidator:
    """Validate weekly meeting capture coverage"""

    def __init__(self):
        """Initialize validator"""
        self.project_root = Path(__file__).parent.parent
        self.logs_dir = self.project_root / "logs"

        self.cred_manager = CredentialManager()
        self.vault_path = self.cred_manager.get_vault_path()
        self.meetings_path = self.vault_path / "00_Inbox" / "Meetings"

        self.stats = {
            "total_granola_meetings": 0,
            "captured_in_obsidian": 0,
            "missing_meetings": [],
            "invalid_meetings_skipped": 0,
            "coverage_percentage": 0.0,
        }
        # Separate typed fields for mypy
        self.total_meetings = 0
        self.captured_count = 0
        self.invalid_count = 0

    def validate_week(self, days: int = 7) -> dict:
        """
        Validate coverage for the past N days

        Args:
            days: Number of days to check (default: 7)

        Returns:
            Dictionary with validation results
        """
        logger.info(f"Starting weekly validation for last {days} days...")

        try:
            # Fetch all Granola meetings from the past week
            granola_meetings = self._fetch_granola_meetings(days)
            self.stats["total_granola_meetings"] = len(granola_meetings)

            # Get all Obsidian meeting files
            obsidian_meetings = self._get_obsidian_meetings(days)

            # Check coverage
            missing = []
            valid_count = 0
            for meeting in granola_meetings:
                if not meeting.get("valid_meeting", True):
                    self.invalid_count += 1
                    continue

                valid_count += 1
                meeting_id = meeting.get("id")
                if not self._meeting_in_obsidian(meeting_id, obsidian_meetings):
                    missing.append(
                        {
                            "id": meeting_id,
                            "title": meeting.get("title", "Untitled"),
                            "created_at": meeting.get("created_at", "unknown"),
                        }
                    )

            self.captured_count = valid_count - len(missing)

            # Update stats dict
            self.stats["invalid_meetings_skipped"] = self.invalid_count
            self.stats["captured_in_obsidian"] = self.captured_count
            self.stats["missing_meetings"] = missing

            # Calculate coverage percentage
            if valid_count > 0:
                coverage = (self.captured_count / valid_count) * 100
                self.stats["coverage_percentage"] = coverage

            result = {
                "timestamp": datetime.now().isoformat(),
                "period_days": days,
                "status": "complete" if len(missing) == 0 else "gaps_detected",
                "stats": self.stats,
            }

            logger.info(f"Validation complete: {self.stats['coverage_percentage']:.1f}% coverage")
            return result

        except Exception as e:
            logger.error(f"Validation error: {e}")
            logger.exception("Detailed error:")
            return {
                "timestamp": datetime.now().isoformat(),
                "period_days": days,
                "status": "error",
                "error": str(e),
                "stats": self.stats,
            }

    def _fetch_granola_meetings(self, days: int) -> list:
        """
        Fetch meetings from Granola API for the past N days

        Args:
            days: Number of days to fetch

        Returns:
            List of meeting dictionaries
        """
        try:
            from granola_fetcher import GranolaFetcher

            fetcher = GranolaFetcher(self.cred_manager)

            # Fetch recent documents (Granola doesn't have date filtering, so fetch more)
            # Estimate: ~5 meetings per day on average
            limit = days * 10
            docs = fetcher.fetch_documents(limit=limit)

            if docs is None:
                logger.error("Failed to fetch documents from Granola API")
                return []

            # Filter to meetings from the past N days
            cutoff_date = datetime.now() - timedelta(days=days)
            recent_meetings = []

            for doc in docs:
                try:
                    created_at = doc.get("created_at")
                    if created_at:
                        created_date = datetime.fromisoformat(created_at.replace("Z", "+00:00"))
                        if created_date.replace(tzinfo=None) >= cutoff_date:
                            recent_meetings.append(doc)
                except Exception as e:
                    logger.debug(f"Error parsing date for doc {doc.get('id')}: {e}")
                    # Include docs with unparsable dates to be safe
                    recent_meetings.append(doc)

            logger.info(f"Found {len(recent_meetings)} Granola meetings from last {days} days")
            return recent_meetings

        except Exception as e:
            logger.error(f"Error fetching Granola meetings: {e}")
            return []

    def _get_obsidian_meetings(self, days: int) -> list:
        """
        Get meeting files from Obsidian for the past N days

        Args:
            days: Number of days to check

        Returns:
            List of Path objects
        """
        if not self.meetings_path.exists():
            logger.warning(f"Meetings directory not found: {self.meetings_path}")
            return []

        cutoff_date = datetime.now() - timedelta(days=days)
        recent_files = []

        for filepath in self.meetings_path.glob("*.md"):
            try:
                # Try to extract date from filename (YYYY-MM-DD format)
                date_str = filepath.name[:10]
                file_date = datetime.strptime(date_str, "%Y-%m-%d")

                if file_date >= cutoff_date:
                    recent_files.append(filepath)
            except ValueError:
                # Skip files that don't match date pattern
                continue

        logger.info(f"Found {len(recent_files)} Obsidian meetings from last {days} days")
        return recent_files

    def _meeting_in_obsidian(self, granola_id: str, obsidian_files: list) -> bool:
        """
        Check if a Granola meeting exists in Obsidian

        Args:
            granola_id: Granola document ID
            obsidian_files: List of Obsidian meeting file paths

        Returns:
            True if found, False otherwise
        """
        for filepath in obsidian_files:
            try:
                with open(filepath, encoding="utf-8") as f:
                    content = f.read()
                    if granola_id in content:
                        return True
            except Exception as e:
                logger.debug(f"Error reading {filepath}: {e}")

        return False

    def generate_report(self, result: dict) -> str:
        """
        Generate human-readable weekly report

        Args:
            result: Validation result dictionary

        Returns:
            Formatted report string (markdown)
        """
        stats = result.get("stats", {})

        lines = []
        lines.append("# Weekly Validation Report")
        lines.append("")
        lines.append(f"**Date**: {datetime.now().strftime('%Y-%m-%d')}")
        lines.append(f"**Period**: Last {result.get('period_days', 7)} days")
        lines.append(f"**Status**: {result.get('status', 'unknown').upper()}")
        lines.append("")

        # Summary
        lines.append("## Summary")
        lines.append("")
        lines.append(f"- **Total meetings in Granola**: {stats.get('total_granola_meetings', 0)}")
        lines.append(f"- **Captured in Obsidian**: {stats.get('captured_in_obsidian', 0)}")
        lines.append(f"- **Invalid meetings skipped**: {stats.get('invalid_meetings_skipped', 0)}")
        lines.append(f"- **Coverage**: {stats.get('coverage_percentage', 0):.1f}%")
        lines.append("")

        # Missing meetings
        missing = stats.get("missing_meetings", [])
        if missing:
            lines.append(f"## ⚠️ Missing Meetings ({len(missing)})")
            lines.append("")
            lines.append("The following meetings were found in Granola but not in Obsidian:")
            lines.append("")
            for meeting in missing:
                lines.append(f"- **{meeting['title']}**")
                lines.append(f"  - ID: `{meeting['id']}`")
                lines.append(f"  - Created: {meeting['created_at']}")
                lines.append("")
        else:
            lines.append("## ✅ Complete Coverage")
            lines.append("")
            lines.append("All meetings from Granola have been captured in Obsidian.")
            lines.append("")

        # Next steps
        lines.append("## Next Steps")
        lines.append("")
        if missing:
            lines.append("1. Review missing meetings list above")
            lines.append("2. Check Granola app to verify these are valid meetings")
            lines.append("3. Manually export missing meetings if needed")
            lines.append("4. Investigate sync failures in logs")
        else:
            lines.append("✓ No action required - system is functioning correctly")
        lines.append("")

        return "\n".join(lines)


def main():
    """Main entry point"""
    import argparse

    # Set up logging
    logging.basicConfig(
        level=logging.INFO,
        format="%(asctime)s - %(levelname)s - %(message)s",
    )

    # Parse arguments
    parser = argparse.ArgumentParser(description="Weekly meeting coverage validation")
    parser.add_argument(
        "--days",
        type=int,
        default=7,
        help="Number of days to validate (default: 7)",
    )
    parser.add_argument(
        "--output",
        type=str,
        help="Output markdown report to file",
    )
    args = parser.parse_args()

    # Run validation
    validator = WeeklyValidator()
    result = validator.validate_week(days=args.days)

    # Generate report
    report = validator.generate_report(result)
    print(report)

    # Save reports
    report_dir = Path(__file__).parent.parent / "logs" / "validation_reports"
    report_dir.mkdir(exist_ok=True)

    timestamp = datetime.now().strftime("%Y-%m-%d")

    # Save markdown report
    report_file = Path(args.output) if args.output else report_dir / f"{timestamp}-validation.md"

    with open(report_file, "w") as f:
        f.write(report)

    logger.info(f"Report saved to: {report_file}")

    # Save JSON result
    json_file = report_dir / f"{timestamp}-validation.json"
    with open(json_file, "w") as f:
        json.dump(result, f, indent=2)

    logger.info(f"JSON result saved to: {json_file}")

    # Exit with appropriate code
    if result["status"] == "error":
        sys.exit(2)
    elif result["status"] == "gaps_detected":
        sys.exit(1)
    else:
        sys.exit(0)


if __name__ == "__main__":
    main()
