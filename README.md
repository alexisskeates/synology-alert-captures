# Synology Alert Captures

Tools for capturing and analyzing Synology NAS webhook notifications for n8n workflow development.

## Structure

```
alerts/                    # Captured webhook payloads (organized by date)
trigger_alerts.py          # SSH-based alert trigger script
trigger_alerts_api.py      # HTTP API-based alert trigger script
requirements.txt           # Python dependencies
```

## Setup

```bash
# Install dependencies
pip install -r requirements.txt

# For SSH script, also install sshpass (optional but recommended)
# macOS:
brew install sshpass
# or build from source: https://sourceforge.net/projects/sshpass/
```

## Usage

### Option 1: HTTP API (Recommended)

Uses direct HTTP API calls - no SSH required.

```bash
# Run all notification tests
python trigger_alerts_api.py --host 192.168.1.100 --user admin

# Use HTTPS (port 5001)
python trigger_alerts_api.py --host 192.168.1.100 --user admin --secure

# Discover available notification APIs
python trigger_alerts_api.py --host 192.168.1.100 --user admin --discover

# Show current notification configuration
python trigger_alerts_api.py --host 192.168.1.100 --user admin --config
```

### Option 2: SSH Script

Uses SSH to run commands directly on the NAS. Requires SSH to be enabled on your Synology.

```bash
# Run all tests
python trigger_alerts.py --host 192.168.1.100 --user admin

# Run specific test only
python trigger_alerts.py --host 192.168.1.100 --user admin --test push

# Send custom notification message
python trigger_alerts.py --host 192.168.1.100 --user admin --custom "Test alert message"

# List available tests
python trigger_alerts.py --list

# Discover APIs on the NAS
python trigger_alerts.py --host 192.168.1.100 --user admin --discover
```

## Alert Types

Based on captured alerts, the following notification types have been observed:

| Type | Example Message |
|------|-----------------|
| Server Offline | `A managed server (185.102.219.107) is offline` |
| CMS Connection Failure | `host01 is unable to connect to the CMS Host (10.10.12.23)` |
| Backup Warning | `Data backup task on host01 partially completed` |
| Test Message | `[STO-BK01] Test Message from STO-BK01` |

## Alert Payload Structure

Webhooks are received as POST requests with this structure:

```json
{
  "headers": {
    "host": "n8n.fourthfloor.solutions",
    "x-forwarded-for": "82.148.62.198",
    "content-type": "application/json"
  },
  "body": {
    "text": "A new system event occurred on your host01 on 11-02-2026 at 21:36.\nA managed server (185.102.219.107) is offline"
  }
}
```

### Message Formats

**Format 1 - Simple:**
```
[<hostname>] <message>
```

**Format 2 - Structured (Synology CMS):**
```
A new system event occurred on your <hostname> on <date> at <time>.
<event message>
```

## Parsing in n8n

To parse the structured format in n8n:

```javascript
// Split message into lines
const lines = $json.body.text.split('\n');

// Parse header line
const headerMatch = lines[0].match(/on your (\w+) on (\d{2}-\d{2}-\d{4}) at (\d{2}:\d{2})/);
const hostname = headerMatch[1];
const date = headerMatch[2];
const time = headerMatch[3];

// Get event message
const eventMessage = lines[1];

// Categorize event type
let eventType = 'unknown';
if (eventMessage.includes('is offline')) eventType = 'server_offline';
else if (eventMessage.includes('unable to connect')) eventType = 'connection_failure';
else if (eventMessage.includes('backup')) eventType = 'backup';
else if (eventMessage.includes('Test')) eventType = 'test';
```

## Synology Prerequisites

1. **Enable SSH** (for SSH script): Control Panel → Terminal & SNMP → Enable SSH
2. **Configure Webhooks**: Control Panel → Notification → Push Service → Manage webhooks
3. **Admin User**: The user must have administrator privileges

## Notification Types Reference

See `notification_types_reference.json` for a complete list of notification types with example payloads.

### Categories

| Category | Event Types |
|----------|-------------|
| **CMS** | server_offline, server_online, cms_connection_failure, cms_connection_restored |
| **Hyper Backup** | backup_completed, backup_partial, backup_failed |
| **Storage** | volume_degraded, volume_crashed, disk_failing, disk_bad_sectors, storage_space_low |
| **Hardware** | ups_power_failure, ups_low_battery, temperature_warning, fan_failure |
| **Security** | login_failed, ip_blocked |
| **System** | test_message, dsm_update_available, system_boot, system_shutdown |
| **Active Backup** | active_backup_completed, active_backup_failed, device_offline |

### Severity Levels

| Level | Description |
|-------|-------------|
| **ERROR** | Critical issues requiring immediate attention |
| **WARN** | Warning conditions that should be monitored |
| **INFO** | Informational messages |

### n8n Parsing Example

```javascript
// Parse Synology notification
const text = $json.body.text;
const lines = text.split('\n');

let hostname, date, time, eventMessage, eventType;

// Check format
if (text.includes('A new system event')) {
  // Structured format
  const match = lines[0].match(/on your ([\w-]+) on (\d{2}-\d{2}-\d{4}) at (\d{2}:\d{2})/);
  hostname = match[1];
  date = match[2];
  time = match[3];
  eventMessage = lines[1];
} else {
  // Simple format: [hostname] message
  const match = text.match(/\[([^\]]+)\] (.+)/);
  hostname = match[1];
  eventMessage = match[2];
}

// Categorize
if (eventMessage.includes('is offline')) eventType = 'server_offline';
else if (eventMessage.includes('unable to connect')) eventType = 'cms_connection_failure';
else if (eventMessage.includes('partially completed')) eventType = 'backup_partial';
else if (eventMessage.includes('Test Message')) eventType = 'test_message';
// ... etc

return { hostname, date, time, eventMessage, eventType };
```

## Troubleshooting

**SSH Connection Failed:**
- Ensure SSH is enabled on your NAS
- Check that the user has admin privileges
- Verify firewall allows SSH (port 22)

**API Login Failed:**
- Check username/password
- Try both HTTP (5000) and HTTPS (5001) ports
- Ensure 2FA is disabled or use OTP

**No Webhooks Received:**
- Verify webhook URL is correctly configured in DSM
- Check n8n webhook is active and listening
- Test with "Send Test Message" button in DSM first
