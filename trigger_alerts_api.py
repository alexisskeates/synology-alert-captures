#!/usr/bin/env python3
"""
Synology Alert Trigger Script (API Version)

Uses the synology-api library to interact with the NAS directly via HTTP API.
This version doesn't require SSH access.

Note: The synology-api library doesn't have built-in test notification methods,
so this script extends it with direct API calls.

Usage:
    python trigger_alerts_api.py --host <NAS_IP> --user <USERNAME> --password <PASSWORD>
"""

import argparse
import requests
import urllib3
import time
import getpass
import json
import sys
from typing import Optional, Any

# Disable SSL warnings for self-signed certs
urllib3.disable_warnings(urllib3.exceptions.InsecureRequestWarning)


class SynologyNotificationTrigger:
    """Class to trigger various notifications on Synology NAS."""

    def __init__(self, host: str, port: int, username: str, password: str, secure: bool = False):
        self.host = host
        self.port = port
        self.username = username
        self.password = password
        self.secure = secure
        self.session_id: Optional[str] = None
        self.base_url = f"{'https' if secure else 'http'}://{host}:{port}/webapi"

    def _request(self, api: str, path: str, method: str, version: int = 1, **params) -> dict:
        """Make an API request to the Synology NAS."""
        url = f"{self.base_url}/{path}"

        data = {
            "api": api,
            "version": version,
            "method": method,
            **params
        }

        if self.session_id:
            data["_sid"] = self.session_id

        try:
            response = requests.post(url, data=data, verify=False, timeout=30)
            response.raise_for_status()
            return response.json()
        except requests.RequestException as e:
            return {"success": False, "error": str(e)}

    def login(self) -> bool:
        """Authenticate with the NAS."""
        print(f"Logging in to {self.host}...")

        result = self._request(
            api="SYNO.API.Auth",
            path="auth.cgi",
            method="login",
            version=6,
            account=self.username,
            passwd=self.password,
            session="NotificationTrigger",
            format="sid"
        )

        if result.get("success"):
            self.session_id = result["data"]["sid"]
            print("  ✓ Login successful")
            return True
        else:
            print(f"  ✗ Login failed: {result.get('error', 'Unknown error')}")
            return False

    def logout(self):
        """Logout from the NAS."""
        if self.session_id:
            self._request(
                api="SYNO.API.Auth",
                path="auth.cgi",
                method="logout",
                version=1,
                session="NotificationTrigger"
            )
            self.session_id = None
            print("Logged out")

    def get_api_info(self) -> dict:
        """Get available API information."""
        return self._request(
            api="SYNO.API.Info",
            path="query.cgi",
            method="query",
            version=1,
            query="all"
        )

    def test_push_notification(self) -> dict:
        """Send a test push notification."""
        print("\n[PUSH] Sending push notification test...")

        result = self._request(
            api="SYNO.Core.Notification.Push",
            path="entry.cgi",
            method="send_test",
            version=1
        )

        if result.get("success"):
            print("  ✓ Push notification test sent")
        else:
            print(f"  ✗ Failed: {result.get('error', result)}")

        return result

    def test_webhook_notification(self, profile_id: int = 1) -> dict:
        """Send a test notification via webhook provider."""
        print(f"\n[WEBHOOK] Sending webhook test (profile_id={profile_id})...")

        result = self._request(
            api="SYNO.Core.Notification.Push.Webhook.Provider",
            path="entry.cgi",
            method="send_test",
            version=2,
            profile_id=profile_id
        )

        if result.get("success"):
            print("  ✓ Webhook notification test sent")
        else:
            print(f"  ✗ Failed: {result.get('error', result)}")

        return result

    def list_webhook_providers(self) -> dict:
        """List configured webhook providers."""
        print("\n[WEBHOOK] Listing webhook providers...")

        result = self._request(
            api="SYNO.Core.Notification.Push.Webhook.Provider",
            path="entry.cgi",
            method="list",
            version=2
        )

        if result.get("success"):
            providers = result.get("data", {}).get("list", [])
            print(f"  ✓ Found {len(providers)} webhook provider(s)")
            for p in providers:
                print(f"    - {p.get('target_name')} (profile_id={p.get('profile_id')})")
        else:
            print(f"  ✗ Failed: {result.get('error', result)}")

        return result

    def test_mail_notification(self) -> dict:
        """Send a test email notification."""
        print("\n[MAIL] Sending email notification test...")

        result = self._request(
            api="SYNO.Core.Notification.Mail",
            path="entry.cgi",
            method="send_test",
            version=1
        )

        if result.get("success"):
            print("  ✓ Email notification test sent")
        else:
            print(f"  ✗ Failed: {result.get('error', result)}")

        return result

    def test_sms_notification(self) -> dict:
        """Send a test SMS notification."""
        print("\n[SMS] Sending SMS notification test...")

        result = self._request(
            api="SYNO.Core.Notification.SMS",
            path="entry.cgi",
            method="send_test",
            version=1
        )

        if result.get("success"):
            print("  ✓ SMS notification test sent")
        else:
            print(f"  ✗ Failed: {result.get('error', result)}")

        return result

    def get_notification_config(self) -> dict:
        """Get current notification configuration."""
        print("\n[CONFIG] Getting notification configuration...")

        configs = {}

        # Push config
        result = self._request(
            api="SYNO.Core.Notification.Push.Conf",
            path="entry.cgi",
            method="get",
            version=1
        )
        configs["push"] = result

        # Mail config
        result = self._request(
            api="SYNO.Core.Notification.Mail.Conf",
            path="entry.cgi",
            method="get",
            version=1
        )
        configs["mail"] = result

        # Webhook config (if available)
        result = self._request(
            api="SYNO.Core.Notification.Webhook",
            path="entry.cgi",
            method="list",
            version=1
        )
        configs["webhook"] = result

        return configs

    def get_active_notifications(self) -> dict:
        """Get active/pending notifications."""
        print("\n[ACTIVE] Getting active notifications...")

        result = self._request(
            api="SYNO.Core.DSMNotify",
            path="entry.cgi",
            method="notify",
            version=1,
            action="load"
        )

        if result.get("success"):
            data = result.get("data", {})
            count = len(data.get("items", []))
            print(f"  ✓ Found {count} active notifications")
        else:
            print(f"  ✗ Failed: {result.get('error', result)}")

        return result

    def get_system_health(self) -> dict:
        """Get system health status."""
        print("\n[HEALTH] Getting system health...")

        result = self._request(
            api="SYNO.Core.System.Status",
            path="entry.cgi",
            method="get",
            version=1
        )

        if result.get("success"):
            print("  ✓ System health retrieved")
        else:
            print(f"  ✗ Failed: {result.get('error', result)}")

        return result

    def list_backup_tasks(self) -> dict:
        """List Hyper Backup tasks."""
        print("\n[BACKUP] Listing backup tasks...")

        result = self._request(
            api="SYNO.Backup.Task",
            path="entry.cgi",
            method="list",
            version=1
        )

        if result.get("success"):
            tasks = result.get("data", {}).get("task_list", [])
            print(f"  ✓ Found {len(tasks)} backup tasks")
            for task in tasks:
                print(f"    - {task.get('name', 'Unknown')} (ID: {task.get('task_id')})")
        else:
            print(f"  ✗ Failed: {result.get('error', result)}")

        return result

    def discover_notification_apis(self) -> list:
        """Discover available notification-related APIs."""
        print("\n[DISCOVER] Discovering notification APIs...")

        api_info = self.get_api_info()
        if not api_info.get("success"):
            print("  ✗ Could not get API info")
            return []

        notification_apis = []
        for api_name, api_data in api_info.get("data", {}).items():
            if any(keyword in api_name.lower() for keyword in ["notif", "alert", "push", "mail", "sms", "webhook"]):
                notification_apis.append({
                    "name": api_name,
                    "path": api_data.get("path"),
                    "minVersion": api_data.get("minVersion"),
                    "maxVersion": api_data.get("maxVersion")
                })

        print(f"  ✓ Found {len(notification_apis)} notification-related APIs:")
        for api in notification_apis:
            print(f"    - {api['name']} (v{api['minVersion']}-{api['maxVersion']})")

        return notification_apis

    def run_all_tests(self, delay: float = 2.0) -> dict:
        """Run all notification tests."""
        results = {
            "webhook": None,
            "push": None,
            "mail": None,
            "sms": None,
            "health": None,
            "active": None
        }

        # List webhook providers first
        providers = self.list_webhook_providers()

        # Test webhook (this is the most reliable method)
        if providers.get("success"):
            provider_list = providers.get("data", {}).get("list", [])
            for provider in provider_list:
                profile_id = provider.get("profile_id", 1)
                results["webhook"] = self.test_webhook_notification(profile_id)
                time.sleep(delay)

        # Try other notification methods (may not be configured)
        results["push"] = self.test_push_notification()
        time.sleep(delay)

        results["sms"] = self.test_sms_notification()
        time.sleep(delay)

        results["health"] = self.get_system_health()
        results["active"] = self.get_active_notifications()

        return results


def main():
    parser = argparse.ArgumentParser(
        description="Trigger Synology NAS notifications via HTTP API",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""
Examples:
    # Run all notification tests
    python trigger_alerts_api.py --host 192.168.1.100 --user admin

    # Use HTTPS (port 5001)
    python trigger_alerts_api.py --host 192.168.1.100 --user admin --secure

    # Discover available APIs
    python trigger_alerts_api.py --host 192.168.1.100 --user admin --discover

    # Get current notification configuration
    python trigger_alerts_api.py --host 192.168.1.100 --user admin --config
        """
    )

    parser.add_argument("--host", "-H", required=True, help="Synology NAS IP or hostname")
    parser.add_argument("--port", "-P", type=int, help="Port (default: 5000 or 5001 for HTTPS)")
    parser.add_argument("--user", "-u", required=True, help="Username")
    parser.add_argument("--password", "-p", help="Password (will prompt if not provided)")
    parser.add_argument("--secure", "-s", action="store_true", help="Use HTTPS")
    parser.add_argument("--discover", action="store_true", help="Discover available APIs")
    parser.add_argument("--config", action="store_true", help="Show notification configuration")
    parser.add_argument("--delay", "-d", type=float, default=2.0, help="Delay between tests (default: 2s)")

    args = parser.parse_args()

    # Set default port based on secure flag
    port = args.port or (5001 if args.secure else 5000)

    # Get password
    password = args.password
    if not password:
        password = getpass.getpass(f"Enter password for {args.user}: ")

    print("="*60)
    print("Synology Notification Trigger (API Version)")
    print("="*60)
    print(f"Host: {args.host}:{port}")
    print(f"User: {args.user}")
    print(f"Secure: {args.secure}")
    print("="*60)

    # Create trigger instance
    trigger = SynologyNotificationTrigger(
        host=args.host,
        port=port,
        username=args.user,
        password=password,
        secure=args.secure
    )

    # Login
    if not trigger.login():
        return 1

    try:
        if args.discover:
            trigger.discover_notification_apis()
        elif args.config:
            config = trigger.get_notification_config()
            print("\nNotification Configuration:")
            print(json.dumps(config, indent=2))
        else:
            # Run all tests
            results = trigger.run_all_tests(delay=args.delay)

            # List backup tasks
            trigger.list_backup_tasks()

            # Summary
            print("\n" + "="*60)
            print("Summary")
            print("="*60)
            success_count = sum(1 for r in results.values() if r and r.get("success"))
            print(f"  Tests completed: {len(results)}")
            print(f"  Successful: {success_count}")
            print("\nCheck your n8n webhook to see captured alerts!")

    finally:
        trigger.logout()

    return 0


if __name__ == "__main__":
    sys.exit(main())
