#!/usr/bin/env python3
"""
Send Mock Synology Alerts to Webhook

Sends mock notification payloads to a webhook URL for testing n8n workflows.

Usage:
    # Send all mock alerts
    python send_mock_alerts.py --webhook <URL>

    # Send specific alert type
    python send_mock_alerts.py --webhook <URL> --type server_offline

    # Send alerts by category
    python send_mock_alerts.py --webhook <URL> --category Storage

    # Send alerts by severity level
    python send_mock_alerts.py --webhook <URL> --level ERROR

    # List available mock alerts
    python send_mock_alerts.py --list
"""

import argparse
import json
import os
import requests
import time
import sys
from pathlib import Path


MOCK_ALERTS_DIR = Path(__file__).parent / "mock_alerts"

# Default webhook URL (your n8n webhook)
DEFAULT_WEBHOOK = "https://n8n.fourthfloor.solutions/webhook/dd771d80-d135-409c-a941-0f2010d7c426"


def load_mock_alerts() -> dict:
    """Load all mock alert files."""
    alerts = {}
    for file in MOCK_ALERTS_DIR.glob("*.json"):
        with open(file) as f:
            alert = json.load(f)
            alerts[file.stem] = alert
    return alerts


def send_alert(webhook_url: str, alert: dict, alert_name: str) -> bool:
    """Send a single alert to the webhook."""
    payload = alert["body"]

    try:
        response = requests.post(
            webhook_url,
            json=payload,
            headers={"Content-Type": "application/json"},
            timeout=10
        )

        if response.status_code in [200, 201, 202, 204]:
            print(f"  ✓ [{alert['level']}] {alert_name}")
            return True
        else:
            print(f"  ✗ [{alert['level']}] {alert_name} - HTTP {response.status_code}")
            return False

    except requests.RequestException as e:
        print(f"  ✗ [{alert['level']}] {alert_name} - {e}")
        return False


def main():
    parser = argparse.ArgumentParser(
        description="Send mock Synology alerts to webhook for testing",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""
Examples:
    # Send all mock alerts
    python send_mock_alerts.py --webhook https://your-webhook-url.com/hook

    # Send only ERROR level alerts
    python send_mock_alerts.py --webhook URL --level ERROR

    # Send only Storage category alerts
    python send_mock_alerts.py --webhook URL --category Storage

    # Send a specific alert type
    python send_mock_alerts.py --webhook URL --type disk_failing

    # Dry run - show what would be sent
    python send_mock_alerts.py --webhook URL --dry-run
        """
    )

    parser.add_argument("--webhook", "-w", default=DEFAULT_WEBHOOK,
                        help=f"Webhook URL (default: {DEFAULT_WEBHOOK[:50]}...)")
    parser.add_argument("--type", "-t", help="Send specific alert type")
    parser.add_argument("--category", "-c", help="Filter by category (CMS, Storage, Hardware, etc.)")
    parser.add_argument("--level", "-l", choices=["INFO", "WARN", "ERROR"],
                        help="Filter by severity level")
    parser.add_argument("--delay", "-d", type=float, default=1.0,
                        help="Delay between alerts in seconds (default: 1)")
    parser.add_argument("--list", action="store_true", help="List available mock alerts")
    parser.add_argument("--dry-run", action="store_true", help="Show what would be sent without sending")

    args = parser.parse_args()

    # Load alerts
    alerts = load_mock_alerts()

    if not alerts:
        print(f"No mock alerts found in {MOCK_ALERTS_DIR}")
        return 1

    # List mode
    if args.list:
        print("Available mock alerts:")
        print("-" * 70)

        # Group by category
        by_category = {}
        for name, alert in alerts.items():
            cat = alert.get("category", "Unknown")
            if cat not in by_category:
                by_category[cat] = []
            by_category[cat].append((name, alert))

        for category in sorted(by_category.keys()):
            print(f"\n{category}:")
            for name, alert in sorted(by_category[category]):
                level = alert.get("level", "?")
                print(f"  [{level:5}] {name}")

        print(f"\nTotal: {len(alerts)} alert types")
        return 0

    # Filter alerts
    filtered = {}
    for name, alert in alerts.items():
        # Filter by type
        if args.type and name != args.type:
            continue
        # Filter by category
        if args.category and alert.get("category", "").lower() != args.category.lower():
            continue
        # Filter by level
        if args.level and alert.get("level") != args.level:
            continue
        filtered[name] = alert

    if not filtered:
        print("No alerts match the specified filters")
        return 1

    # Send alerts
    print("="*70)
    print(f"Sending {len(filtered)} mock alert(s) to webhook")
    print(f"Webhook: {args.webhook[:60]}...")
    print("="*70)

    if args.dry_run:
        print("\n[DRY RUN - Not actually sending]\n")

    results = {"success": 0, "failed": 0}

    for name, alert in sorted(filtered.items()):
        if args.dry_run:
            print(f"  Would send: [{alert['level']}] {name}")
            print(f"    Payload: {json.dumps(alert['body'])[:80]}...")
            results["success"] += 1
        else:
            if send_alert(args.webhook, alert, name):
                results["success"] += 1
            else:
                results["failed"] += 1

            if args.delay > 0 and name != list(filtered.keys())[-1]:
                time.sleep(args.delay)

    # Summary
    print("\n" + "="*70)
    print("Summary")
    print("="*70)
    print(f"  Sent: {results['success']}")
    print(f"  Failed: {results['failed']}")

    if not args.dry_run:
        print("\nCheck your n8n workflow for the received alerts!")

    return 0 if results["failed"] == 0 else 1


if __name__ == "__main__":
    sys.exit(main())
