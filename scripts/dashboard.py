#!/usr/bin/env -S uv run --quiet python
"""
Monitoring Dashboard

Simple CLI dashboard showing current system status at a glance.
Run this anytime to check system health.
"""

import json
import logging
import sys
from datetime import datetime
from pathlib import Path
from typing import Any

# Add src to path
sys.path.insert(0, str(Path(__file__).parent.parent / "src"))

logger = logging.getLogger(__name__)


def load_status_file(project_root: Path) -> dict[str, Any] | None:
    """Load last sync status"""
    status_file = project_root / "logs" / "status.json"
    if not status_file.exists():
        return None

    try:
        with open(status_file) as f:
            return json.load(f)  # type: ignore[no-any-return]
    except Exception:
        return None


def load_latest_health(project_root: Path) -> dict[str, Any] | None:
    """Load latest health check result"""
    health_dir = project_root / "logs" / "health_reports"
    if not health_dir.exists():
        return None

    # Find most recent health JSON file
    json_files = sorted(health_dir.glob("*-health.json"), reverse=True)
    if not json_files:
        return None

    try:
        with open(json_files[0]) as f:
            return json.load(f)  # type: ignore[no-any-return]
    except Exception:
        return None


def load_latest_validation(project_root: Path) -> dict[str, Any] | None:
    """Load latest validation report"""
    val_dir = project_root / "logs" / "validation_reports"
    if not val_dir.exists():
        return None

    # Find most recent validation JSON file
    json_files = sorted(val_dir.glob("*-validation.json"), reverse=True)
    if not json_files:
        return None

    try:
        with open(json_files[0]) as f:
            return json.load(f)  # type: ignore[no-any-return]
    except Exception:
        return None


def format_time_ago(timestamp_str: str) -> str:
    """Format timestamp as 'X minutes/hours ago'"""
    try:
        ts = datetime.fromisoformat(timestamp_str)
        delta = datetime.now() - ts

        if delta.total_seconds() < 60:
            return "just now"
        if delta.total_seconds() < 3600:
            mins = int(delta.total_seconds() / 60)
            return f"{mins} min{'s' if mins != 1 else ''} ago"
        if delta.total_seconds() < 86400:
            hours = int(delta.total_seconds() / 3600)
            return f"{hours} hour{'s' if hours != 1 else ''} ago"
        days = int(delta.total_seconds() / 86400)
        return f"{days} day{'s' if days != 1 else ''} ago"
    except Exception:
        return "unknown"


def get_status_indicator(status: str) -> str:
    """Get emoji indicator for status"""
    status_map = {
        "healthy": "🟢",
        "degraded": "🟡",
        "unhealthy": "🔴",
        "complete": "✅",
        "gaps_detected": "⚠️",
        "error": "❌",
    }
    return status_map.get(status.lower(), "❓")


def print_dashboard():
    """Print monitoring dashboard"""
    project_root = Path(__file__).parent.parent

    # Header
    print()
    print("=" * 70)
    print(" " * 20 + "GRANOLA SYNC - MONITORING DASHBOARD")
    print("=" * 70)
    print()
    print(f"Generated: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}")
    print()

    # Last Sync Status
    print("┌─ LAST SYNC " + "─" * 56)
    status = load_status_file(project_root)
    if status:
        last_run = status.get("last_run", "unknown")
        print(f"│ Time:      {last_run}  ({format_time_ago(last_run)})")
        print(f"│ Fetched:   {status.get('fetched', 0)} documents")
        print(f"│ Processed: {status.get('processed', 0)} notes")
        print(f"│ Failed:    {status.get('failed', 0)}")
        print(
            f"│ Status:    {get_status_indicator('healthy' if status.get('failed', 0) == 0 else 'degraded')} {'OK' if status.get('failed', 0) == 0 else 'ERRORS'}"
        )
    else:
        print("│ No sync status available")
    print("└" + "─" * 68)
    print()

    # Health Check
    print("┌─ HEALTH CHECK " + "─" * 53)
    health = load_latest_health(project_root)
    if health:
        print(
            f"│ Status:           {get_status_indicator(health.get('status', 'unknown'))} {health.get('status', 'unknown').upper()}"
        )
        print(f"│ Last Check:       {format_time_ago(health.get('timestamp', ''))}")

        metrics = health.get("metrics", {})
        if metrics:
            print(
                f"│ API Status:       {get_status_indicator('healthy' if metrics.get('granola_api') == 'accessible' else 'unhealthy')} {metrics.get('granola_api', 'unknown')}"
            )
            print(f"│ Total Meetings:   {metrics.get('total_meetings', 0)}")
            print(f"│ Last 7 Days:      {metrics.get('meetings_last_7_days', 0)}")
            print(
                f"│ Disk Free:        {metrics.get('disk_free_gb', 0):.1f} GB ({metrics.get('disk_percent_free', 0):.1f}%)"
            )

        issues = health.get("issues", [])
        warnings = health.get("warnings", [])

        if issues:
            print(f"│ Issues:           {len(issues)} critical")
            for issue in issues[:2]:  # Show first 2
                print(f"│   • {issue}")
        if warnings:
            print(f"│ Warnings:         {len(warnings)}")
    else:
        print("│ No health check data available")
        print("│ Run: ./scripts/health_check.py")
    print("└" + "─" * 68)
    print()

    # Weekly Validation
    print("┌─ WEEKLY VALIDATION " + "─" * 48)
    validation = load_latest_validation(project_root)
    if validation:
        stats = validation.get("stats", {})
        print(
            f"│ Status:           {get_status_indicator(validation.get('status', 'unknown'))} {validation.get('status', 'unknown').replace('_', ' ').upper()}"
        )
        print(f"│ Last Check:       {format_time_ago(validation.get('timestamp', ''))}")
        print(f"│ Period:           {validation.get('period_days', 7)} days")
        print(f"│ Total Meetings:   {stats.get('total_granola_meetings', 0)}")
        print(f"│ Captured:         {stats.get('captured_in_obsidian', 0)}")
        print(f"│ Coverage:         {stats.get('coverage_percentage', 0):.1f}%")

        missing = stats.get("missing_meetings", [])
        if missing:
            print(f"│ Missing:          {len(missing)} meetings")
            for meeting in missing[:2]:  # Show first 2
                print(f"│   • {meeting.get('title', 'Unknown')}")
    else:
        print("│ No validation data available")
        print("│ Run: ./scripts/weekly_validation.py")
    print("└" + "─" * 68)
    print()

    # Quick Actions
    print("┌─ QUICK ACTIONS " + "─" * 52)
    print("│ Health Check:     ./scripts/health_check.py")
    print("│ Weekly Report:    ./scripts/weekly_validation.py")
    print("│ Manual Sync:      ./scripts/granola_sync.py")
    print("│ View Logs:        tail -f logs/cron.log")
    print("│ Check Status:     cat logs/status.json")
    print("└" + "─" * 68)
    print()


def main():
    """Main entry point"""
    # Minimal logging
    logging.basicConfig(level=logging.WARNING)

    try:
        print_dashboard()
    except KeyboardInterrupt:
        print("\n")
        sys.exit(0)
    except Exception as e:
        print(f"\n❌ Error generating dashboard: {e}\n")
        sys.exit(1)


if __name__ == "__main__":
    main()
