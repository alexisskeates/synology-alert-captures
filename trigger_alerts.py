#!/usr/bin/env python3
"""
Synology Alert Trigger Script

Triggers various test notifications on a Synology NAS via SSH
to capture webhook payloads for n8n workflow development.

Usage:
    python trigger_alerts.py --host <NAS_IP> --user <USERNAME> [--password <PASSWORD>]

If password is not provided, you'll be prompted to enter it.
"""

import argparse
import subprocess
import time
import getpass
import sys
# Known Synology notification APIs and their test methods
NOTIFICATION_TESTS = {
    "push": {
        "api": "SYNO.Core.Notification.Push",
        "method": "send_test",
        "version": 1,
        "description": "Push notification test"
    },
    "mail": {
        "api": "SYNO.Core.Notification.Mail",
        "method": "send_test",
        "version": 1,
        "description": "Email notification test"
    },
    "sms": {
        "api": "SYNO.Core.Notification.SMS",
        "method": "send_test",
        "version": 1,
        "description": "SMS notification test"
    },
    "push_mail": {
        "api": "SYNO.Core.Notification.Push.Mail",
        "method": "send_test",
        "version": 1,
        "description": "Push mail notification test"
    },
}

# Additional API commands to explore (may or may not have test methods)
EXPLORATORY_APIS = [
    "SYNO.Core.Notification.Webhook",
    "SYNO.Core.DSMNotify",
    "SYNO.Backup.Task",
    "SYNO.Core.System",
    "SYNO.SurveillanceStation.Notification",
]


def run_ssh_command(host: str, user: str, password: str, command: str, use_sudo: bool = True) -> tuple[int, str, str]:
    """
    Run a command on the Synology NAS via SSH.

    Returns:
        tuple: (return_code, stdout, stderr)
    """
    if use_sudo:
        command = f"sudo {command}"

    ssh_command = [
        "sshpass", "-p", password,
        "ssh", "-o", "StrictHostKeyChecking=no",
        "-o", "UserKnownHostsFile=/dev/null",
        f"{user}@{host}",
        command
    ]

    try:
        result = subprocess.run(
            ssh_command,
            capture_output=True,
            text=True,
            timeout=30
        )
        return result.returncode, result.stdout, result.stderr
    except subprocess.TimeoutExpired:
        return -1, "", "Command timed out"
    except FileNotFoundError:
        # sshpass not installed, try with expect or manual
        return run_ssh_without_sshpass(host, user, command)


def run_ssh_without_sshpass(host: str, user: str, command: str) -> tuple[int, str, str]:
    """
    Fallback SSH method when sshpass is not available.
    Uses subprocess with stdin for password (less reliable).
    """
    print("  [Note: sshpass not found, using basic SSH - you may need to enter password manually]")

    ssh_command = [
        "ssh", "-o", "StrictHostKeyChecking=no",
        "-o", "UserKnownHostsFile=/dev/null",
        f"{user}@{host}",
        command
    ]

    try:
        result = subprocess.run(
            ssh_command,
            capture_output=True,
            text=True,
            timeout=30
        )
        return result.returncode, result.stdout, result.stderr
    except subprocess.TimeoutExpired:
        return -1, "", "Command timed out"


def test_ssh_connection(host: str, user: str, password: str) -> bool:
    """Test if SSH connection works."""
    print(f"Testing SSH connection to {host}...")
    code, stdout, stderr = run_ssh_command(host, user, password, "echo 'Connection successful'", use_sudo=False)

    if code == 0 and "successful" in stdout:
        print("  ✓ SSH connection successful")
        return True
    else:
        print(f"  ✗ SSH connection failed: {stderr}")
        return False


def trigger_notification_test(host: str, user: str, password: str, test_name: str, test_config: dict) -> bool:
    """Trigger a specific notification test."""
    api = test_config["api"]
    method = test_config["method"]
    version = test_config["version"]
    description = test_config["description"]

    print(f"\n[{test_name.upper()}] {description}")
    print(f"  API: {api}")
    print(f"  Method: {method}")

    command = f'synowebapi --exec api={api} method={method} --version={version}'

    code, stdout, stderr = run_ssh_command(host, user, password, command)

    if code == 0:
        print(f"  ✓ Success: {stdout.strip()}")
        return True
    else:
        print(f"  ✗ Failed: {stderr.strip() or stdout.strip()}")
        return False


def list_available_apis(host: str, user: str, password: str):
    """List available notification-related APIs on the NAS."""
    print("\n" + "="*60)
    print("Discovering available APIs...")
    print("="*60)

    # Try to get API info
    command = 'synowebapi --exec api=SYNO.API.Info method=query --version=1 2>/dev/null | grep -i notif'
    _, stdout, _ = run_ssh_command(host, user, password, command)

    if stdout:
        print("Found notification-related APIs:")
        print(stdout)
    else:
        print("Could not enumerate APIs (this is normal on some DSM versions)")


def trigger_backup_event(host: str, user: str, password: str):
    """Attempt to trigger a backup-related notification."""
    print("\n[BACKUP] Checking backup tasks...")

    # List backup tasks
    command = 'synowebapi --exec api=SYNO.Backup.Task method=list --version=1'
    code, stdout, stderr = run_ssh_command(host, user, password, command)

    if code == 0:
        print(f"  Backup tasks found: {len(stdout.strip())} bytes response")
    else:
        print(f"  Could not list backup tasks: {stderr.strip()}")


def trigger_system_health_check(host: str, user: str, password: str):
    """Trigger system health notification."""
    print("\n[HEALTH] Triggering system health check...")

    command = 'synowebapi --exec api=SYNO.Core.System.Status method=get --version=1'
    code, _, stderr = run_ssh_command(host, user, password, command)

    if code == 0:
        print("  ✓ Health check completed")
    else:
        print(f"  ✗ Failed: {stderr.strip()}")


def send_custom_webhook_test(host: str, user: str, password: str, message: str):
    """
    Send a custom test message via curl to simulate a webhook.
    This requires knowing the webhook URL configured in DSM.
    """
    print(f"\n[CUSTOM] Sending custom message: {message}")

    # Try using synodsmnotify command (DSM notification utility)
    command = f'synodsmnotify -c "@administrators" "Test Alert" "{message}"'
    code, _, stderr = run_ssh_command(host, user, password, command)

    if code == 0:
        print("  ✓ Custom notification sent")
        return True
    else:
        print("  ✗ synodsmnotify failed, trying alternative...")

        # Alternative: use synonotify
        command = f'synonotify PKGHasUpgrade "{{"title": "Test", "message": "{message}"}}"'
        code, _, stderr = run_ssh_command(host, user, password, command)

        if code == 0:
            print("  ✓ Alternative notification sent")
            return True
        else:
            print(f"  ✗ Failed: {stderr.strip() or 'Unknown error'}")
            return False


def main():
    parser = argparse.ArgumentParser(
        description="Trigger Synology NAS notifications for webhook testing",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""
Examples:
    # Run all tests
    python trigger_alerts.py --host 192.168.1.100 --user admin

    # Run specific test only
    python trigger_alerts.py --host 192.168.1.100 --user admin --test push

    # Send custom message
    python trigger_alerts.py --host 192.168.1.100 --user admin --custom "Test alert message"

    # List available tests
    python trigger_alerts.py --list
        """
    )

    parser.add_argument("--host", "-H", help="Synology NAS IP address or hostname")
    parser.add_argument("--user", "-u", help="SSH username (usually admin)")
    parser.add_argument("--password", "-p", help="SSH password (will prompt if not provided)")
    parser.add_argument("--test", "-t", choices=list(NOTIFICATION_TESTS.keys()) + ["all"],
                        default="all", help="Specific test to run (default: all)")
    parser.add_argument("--custom", "-c", help="Send a custom notification message")
    parser.add_argument("--list", "-l", action="store_true", help="List available tests")
    parser.add_argument("--delay", "-d", type=float, default=2.0,
                        help="Delay between tests in seconds (default: 2)")
    parser.add_argument("--discover", action="store_true", help="Discover available APIs")

    args = parser.parse_args()

    # List tests and exit
    if args.list:
        print("Available notification tests:")
        print("-" * 50)
        for name, config in NOTIFICATION_TESTS.items():
            print(f"  {name:12} - {config['description']}")
            print(f"               API: {config['api']}")
        return 0

    # Validate required args
    if not args.host or not args.user:
        parser.error("--host and --user are required")

    # Get password
    password = args.password
    if not password:
        password = getpass.getpass(f"Enter SSH password for {args.user}@{args.host}: ")

    print("="*60)
    print("Synology Alert Trigger Script")
    print("="*60)
    print(f"Host: {args.host}")
    print(f"User: {args.user}")
    print("="*60)

    # Test connection
    if not test_ssh_connection(args.host, args.user, password):
        print("\nFailed to connect. Please check:")
        print("  - SSH is enabled on your NAS (Control Panel → Terminal & SNMP)")
        print("  - Username and password are correct")
        print("  - The user has admin privileges")
        return 1

    # Discover APIs if requested
    if args.discover:
        list_available_apis(args.host, args.user, password)

    # Send custom message if provided
    if args.custom:
        send_custom_webhook_test(args.host, args.user, password, args.custom)
        return 0

    # Run tests
    results = {"success": 0, "failed": 0}

    if args.test == "all":
        tests_to_run = NOTIFICATION_TESTS.items()
    else:
        tests_to_run = [(args.test, NOTIFICATION_TESTS[args.test])]

    for test_name, test_config in tests_to_run:
        success = trigger_notification_test(args.host, args.user, password, test_name, test_config)

        if success:
            results["success"] += 1
        else:
            results["failed"] += 1

        # Delay between tests
        if args.delay > 0:
            time.sleep(args.delay)

    # Additional checks
    trigger_system_health_check(args.host, args.user, password)
    trigger_backup_event(args.host, args.user, password)

    # Summary
    print("\n" + "="*60)
    print("Summary")
    print("="*60)
    print(f"  Successful: {results['success']}")
    print(f"  Failed:     {results['failed']}")
    print("\nCheck your n8n webhook to see captured alerts!")

    return 0 if results["failed"] == 0 else 1


if __name__ == "__main__":
    sys.exit(main())
