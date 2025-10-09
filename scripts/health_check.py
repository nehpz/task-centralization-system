#!/usr/bin/env -S uv run --quiet python
"""
Health Check Script

Monitors the health of the Granola sync system and alerts if issues are detected.
Run this periodically (daily) to ensure system is functioning correctly.
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


class HealthChecker:
    """Check system health and generate reports"""

    def __init__(self):
        """Initialize health checker"""
        self.project_root = Path(__file__).parent.parent
        self.logs_dir = self.project_root / "logs"
        self.status_file = self.logs_dir / "status.json"
        self.cron_log = self.logs_dir / "cron.log"
        self.sync_log = self.logs_dir / "granola_sync.log"

        self.cred_manager = CredentialManager()
        self.vault_path = self.cred_manager.get_vault_path()
        self.meetings_path = self.vault_path / "00_Inbox" / "Meetings"

        self.issues = []
        self.warnings = []
        self.metrics = {}

    def check_all(self) -> dict:
        """
        Run all health checks

        Returns:
            Dictionary with check results
        """
        logger.info("Starting health check...")

        # Run all checks
        self.check_credentials()
        self.check_last_sync()
        self.check_recent_meetings()
        self.check_cron_errors()
        self.check_disk_space()
        self.check_api_connectivity()

        # Calculate overall health
        if len(self.issues) == 0:
            status = "healthy"
        elif len(self.issues) <= 2:
            status = "degraded"
        else:
            status = "unhealthy"

        result = {
            "timestamp": datetime.now().isoformat(),
            "status": status,
            "issues": self.issues,
            "warnings": self.warnings,
            "metrics": self.metrics,
        }

        logger.info(f"Health check complete: {status}")
        return result

    def check_credentials(self):
        """Check that all credentials are configured"""
        logger.debug("Checking credentials...")

        # Check Granola token
        granola_token = self.cred_manager.get_granola_token()
        if not granola_token:
            self.issues.append("Granola credentials missing or invalid")
        else:
            self.metrics["granola_credentials"] = "configured"

        # Check LLM config (optional)
        llm_config = self.cred_manager.get_llm_config()
        if llm_config:
            self.metrics["llm_provider"] = llm_config.get("provider", "unknown")
            self.metrics["llm_model"] = llm_config.get("model", "unknown")
        else:
            self.warnings.append("LLM credentials not configured (enrichment disabled)")

        # Check vault path
        if not self.vault_path.exists():
            self.issues.append(f"Vault path does not exist: {self.vault_path}")
        else:
            self.metrics["vault_path"] = str(self.vault_path)

    def check_last_sync(self):
        """Check when the last sync occurred"""
        logger.debug("Checking last sync time...")

        if not self.status_file.exists():
            self.warnings.append("No status file found (sync may not have run yet)")
            return

        try:
            with open(self.status_file) as f:
                status = json.load(f)

            last_run = status.get("last_run")
            if not last_run:
                self.warnings.append("Status file missing last_run timestamp")
                return

            last_run_time = datetime.fromisoformat(last_run)
            time_since_sync = datetime.now() - last_run_time

            self.metrics["last_sync"] = last_run
            self.metrics["minutes_since_sync"] = int(time_since_sync.total_seconds() / 60)

            # Alert if last sync was more than 1 hour ago
            if time_since_sync > timedelta(hours=1):
                self.issues.append(
                    f"Last sync was {time_since_sync.total_seconds() / 3600:.1f} hours ago"
                )

            # Check for failures
            failed = status.get("failed", 0)
            if failed > 0:
                self.warnings.append(f"Last sync had {failed} failures")

            # Store sync metrics
            self.metrics["last_sync_fetched"] = status.get("fetched", 0)
            self.metrics["last_sync_processed"] = status.get("processed", 0)
            self.metrics["last_sync_failed"] = status.get("failed", 0)

        except Exception as e:
            self.warnings.append(f"Error reading status file: {e}")

    def check_recent_meetings(self):
        """Check that meetings have been captured recently"""
        logger.debug("Checking recent meetings...")

        if not self.meetings_path.exists():
            self.issues.append(f"Meetings directory does not exist: {self.meetings_path}")
            return

        try:
            # Get all meeting files
            meeting_files = list(self.meetings_path.glob("*.md"))
            self.metrics["total_meetings"] = len(meeting_files)

            if len(meeting_files) == 0:
                self.warnings.append("No meeting notes found in vault")
                return

            # Check for meetings from today
            today = datetime.now().strftime("%Y-%m-%d")
            today_meetings = [f for f in meeting_files if f.name.startswith(today)]
            self.metrics["meetings_today"] = len(today_meetings)

            # Check for meetings from last 7 days
            week_ago = datetime.now() - timedelta(days=7)
            recent_meetings = []
            for f in meeting_files:
                try:
                    # Extract date from filename (YYYY-MM-DD format)
                    date_str = f.name[:10]
                    file_date = datetime.strptime(date_str, "%Y-%m-%d")
                    if file_date >= week_ago:
                        recent_meetings.append(f)
                except ValueError:
                    # Skip files that don't match date pattern
                    continue

            self.metrics["meetings_last_7_days"] = len(recent_meetings)

            if len(recent_meetings) == 0:
                self.warnings.append("No meetings captured in the last 7 days")

        except Exception as e:
            self.warnings.append(f"Error checking meeting files: {e}")

    def check_cron_errors(self):
        """Check cron log for recent errors"""
        logger.debug("Checking cron log for errors...")

        if not self.cron_log.exists():
            self.warnings.append("Cron log file not found")
            return

        try:
            # Read last 100 lines of cron log
            with open(self.cron_log) as f:
                lines = f.readlines()[-100:]

            # Count error occurrences
            error_count = sum(1 for line in lines if "ERROR" in line or "Error" in line)
            uv_errors = sum(1 for line in lines if "uv: No such file" in line)

            if uv_errors > 0:
                self.issues.append(f"UV path errors detected in cron log ({uv_errors} occurrences)")

            if error_count > 10:
                self.warnings.append(f"High error count in cron log ({error_count} errors)")

            self.metrics["recent_cron_errors"] = error_count

        except Exception as e:
            self.warnings.append(f"Error reading cron log: {e}")

    def check_disk_space(self):
        """Check available disk space"""
        logger.debug("Checking disk space...")

        try:
            import shutil

            stats = shutil.disk_usage(self.project_root)
            free_gb = stats.free / (1024**3)
            total_gb = stats.total / (1024**3)
            percent_free = (stats.free / stats.total) * 100

            self.metrics["disk_free_gb"] = round(free_gb, 2)
            self.metrics["disk_total_gb"] = round(total_gb, 2)
            self.metrics["disk_percent_free"] = round(percent_free, 1)

            # Alert if less than 10% or 5GB free
            if percent_free < 10 or free_gb < 5:
                self.issues.append(f"Low disk space: {free_gb:.1f}GB free ({percent_free:.1f}%)")

        except Exception as e:
            self.warnings.append(f"Error checking disk space: {e}")

    def check_api_connectivity(self):
        """Check connectivity to Granola API"""
        logger.debug("Checking API connectivity...")

        try:
            from granola_fetcher import GranolaFetcher

            fetcher = GranolaFetcher(self.cred_manager)

            # Try to fetch recent documents (limit 1 to be fast)
            docs = fetcher.fetch_documents(limit=1)

            if docs is not None:
                self.metrics["granola_api"] = "accessible"
                self.metrics["granola_api_docs_count"] = len(docs)
            else:
                self.issues.append("Granola API request failed")
                self.metrics["granola_api"] = "inaccessible"

        except Exception as e:
            self.issues.append(f"Granola API connectivity error: {e}")
            self.metrics["granola_api"] = "error"

    def generate_report(self, result: dict) -> str:
        """
        Generate human-readable health report

        Args:
            result: Health check result dictionary

        Returns:
            Formatted report string
        """
        lines = []
        lines.append("=" * 60)
        lines.append("Granola Sync - Health Check Report")
        lines.append("=" * 60)
        lines.append(f"Timestamp: {result['timestamp']}")
        lines.append(f"Status: {result['status'].upper()}")
        lines.append("")

        # Metrics
        if result["metrics"]:
            lines.append("Metrics:")
            for key, value in result["metrics"].items():
                lines.append(f"  {key}: {value}")
            lines.append("")

        # Issues
        if result["issues"]:
            lines.append(f"Issues Found ({len(result['issues'])}):")
            for issue in result["issues"]:
                lines.append(f"  ✗ {issue}")
            lines.append("")
        else:
            lines.append("✓ No critical issues found")
            lines.append("")

        # Warnings
        if result["warnings"]:
            lines.append(f"Warnings ({len(result['warnings'])}):")
            for warning in result["warnings"]:
                lines.append(f"  ⚠ {warning}")
            lines.append("")

        lines.append("=" * 60)
        return "\n".join(lines)


def main():
    """Main entry point"""
    # Set up logging
    logging.basicConfig(
        level=logging.INFO,
        format="%(asctime)s - %(levelname)s - %(message)s",
    )

    # Run health check
    checker = HealthChecker()
    result = checker.check_all()

    # Generate report
    report = checker.generate_report(result)
    print(report)

    # Save report to file
    report_dir = Path(__file__).parent.parent / "logs" / "health_reports"
    report_dir.mkdir(exist_ok=True)

    timestamp = datetime.now().strftime("%Y-%m-%d")
    report_file = report_dir / f"{timestamp}-health.txt"

    with open(report_file, "w") as f:
        f.write(report)

    logger.info(f"Report saved to: {report_file}")

    # Save JSON result
    json_file = report_dir / f"{timestamp}-health.json"
    with open(json_file, "w") as f:
        json.dump(result, f, indent=2)

    logger.info(f"JSON result saved to: {json_file}")

    # Exit with appropriate code
    if result["status"] == "unhealthy":
        sys.exit(2)  # Critical issues
    elif result["status"] == "degraded":
        sys.exit(1)  # Minor issues
    else:
        sys.exit(0)  # Healthy


if __name__ == "__main__":
    main()
