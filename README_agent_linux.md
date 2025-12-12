# NexHub Agent for Linux

A lightweight, zero-dependency Python agent for collecting system information and submitting it to the NexHub API.

## Features

- **Zero Dependencies**: Uses only Python 3 standard library (urllib, no external packages required)
- **Comprehensive Data Collection**:
  - System identification (hostname, UUID, manufacturer, model)
  - CPU information (model, cores, threads, sockets)
  - Memory details (total, individual DIMMs with speed/manufacturer)
  - Disk information (physical disks with size, model, usage)
  - Network interfaces (via lspci)
  - Expansion slots (PCIe slots from dmidecode)
  - Accelerators (GPUs/graphics cards)
  - BIOS/firmware information
  - OS details (distribution, version, kernel)
  - BMC/IPMI information (if available)
- **Smart Updates**: Uses UUID to identify servers and update existing records
- **Dry-Run Mode**: Preview collected data without submitting to API
- **Verbose Logging**: Detailed output for troubleshooting
- **Error Handling**: Graceful failure with clear error messages

## Requirements

- **Python**: 3.6 or higher (3.12+ recommended)
- **Privileges**: Root/sudo access for complete hardware information
- **Commands** (usually pre-installed on Linux):
  - `dmidecode` - Hardware information
  - `lscpu` - CPU details
  - `lsblk` - Block device information
  - `fdisk` - Disk partition information
  - `df` - Disk usage statistics
  - `lspci` - PCI device enumeration
  - `hostnamectl` - System hostname and OS info
  - `ipmitool` (optional) - BMC/IPMI information

## Installation

1. **Copy the agent to your system** (optional):
   ```bash
   sudo cp agent_linux.py /usr/local/bin/agent_linux.py
   sudo chmod +x /usr/local/bin/agent_linux.py
   ```
   
   Or just run it directly from the repository directory.

2. **Verify Python version**:
   ```bash
   python3 --version  # Should be 3.6 or higher
   ```

3. **Test data collection** (dry-run, no API needed):
   ```bash
   sudo python3 agent_linux.py --dry-run --url dummy --token dummy
   ```

## Usage

### Basic Commands

#### 1. Dry Run (Preview Data Without Submitting)
Test data collection and verify output format without contacting the API:

```bash
sudo python3 agent_linux.py --dry-run --url dummy --token dummy
```

**Output**:
```
================================================================================
DRY RUN MODE - DATA COLLECTION PREVIEW
================================================================================

Collected System Information:
--------------------------------------------------------------------------------

[+] BASIC INFO:
   Hostname:     ubuntu-server-01
   UUID:         8c178819-2df5-3be8-4a9f-169e2a10f205
   IP Address:   192.168.1.100
   Manufacturer: Dell Inc.
   Product:      PowerEdge R740
   Serial:       ABC123XYZ

[+] CPU INFO:
   Model:        Intel Xeon Gold 6140
   Cores:        36
   Sockets:      2

[+] MEMORY:
   Total:        128 GB
   Slots:        8 populated

[+] DISK:
   Disks:        4 physical disk(s)

[+] NETWORK INTERFACES:
   Count:        4 interface(s)

[+] EXPANSION SLOTS:
   Count:        8 slot(s)

[+] ACCELERATORS:
   Count:        2 device(s)

================================================================================
✓ Data collection successful!
  Run without --dry-run to submit this data to the API
================================================================================
```

#### 2. Dry Run with Full JSON Output
View complete JSON data structure:

```bash
sudo python3 agent_linux.py --dry-run --verbose --url dummy --token dummy
```

This displays both the formatted summary and the complete JSON payload.

#### 3. Submit Data to API
Collect and submit data to your NexHub server:

```bash
sudo python3 agent_linux.py --url http://nexhub.example.com --token YOUR_API_TOKEN
```

**Success Output**:
```
Collecting system information...

Submitting to http://nexhub.example.com...

✓ Successfully submitted server data
```

#### 4. Submit with Verbose Output
See the complete API response:

```bash
sudo python3 agent_linux.py --url http://nexhub.example.com --token YOUR_API_TOKEN --verbose
```

### Command-Line Options

```
--url URL              NexHub base URL (e.g., http://nexhub.example.com)
--token TOKEN          API authentication token
--dry-run              Preview collected data without submitting to API
--verbose, -v          Show detailed output and full JSON data
--log-file PATH        Log file path (default: /var/log/overwatch-agent.log)
--config PATH          Configuration file path (default: sys_cfg.ini)
```

## Configuration File

The agent supports a minimal configuration file `sys_cfg.ini` for **hardware overrides only**. These overrides are used when auto-detection fails (e.g., CPU returns "@0000" or "To Be Filled").

```ini
[hardware]
# CPU model override (used when dmidecode returns @0000 or invalid data)
cpu = Intel(R) Xeon(R) Gold 6140 CPU @ 2.30GHz

# Manufacturer override (if dmidecode fails)
manufacture = Dell Inc.

# Product name override
product_name = PowerEdge R740
```

**Important Notes:**
- These are **fallback values only** - used when auto-detection fails
- Leave empty to use auto-detected values (recommended)
- UUID, hostname, IP, MAC are always auto-detected and **cannot be overridden**
- All other system info (memory, disks, BIOS, OS) is always auto-collected
- The agent will look for `sys_cfg.ini` in the current directory or use the path specified with `--config`

## API Token

To get an API token:

1. Log in to NexHub web interface
2. Go to Django Admin → Auth Tokens
3. Create a new token or copy existing one
4. Use this token with the `--token` parameter

## Automated Collection (Cron)

Schedule the agent to run automatically and keep your inventory up-to-date:

### Hourly Updates
```bash
# Edit crontab
sudo crontab -e

# Add this line (runs every hour)
0 * * * * /usr/bin/python3 /path/to/agent_linux.py --url http://nexhub.example.com --token YOUR_TOKEN >> /var/log/nexhub-agent-cron.log 2>&1
```

### Daily Updates
```bash
# Run once per day at 2 AM
0 2 * * * /usr/bin/python3 /path/to/agent_linux.py --url http://nexhub.example.com --token YOUR_TOKEN >> /var/log/nexhub-agent-cron.log 2>&1
```

### With Error Notifications
```bash
# Email on failure
0 * * * * /usr/bin/python3 /path/to/agent_linux.py --url http://nexhub.example.com --token YOUR_TOKEN || echo "NexHub agent failed on $(hostname)" | mail -s "Agent Error" admin@example.com
```

## Collected Data Structure

The agent collects and submits the following JSON structure:

```json
{
  "hostname": "ubuntu-server-01",
  "ip_address": "192.168.1.100",
  "uuid": "8c178819-2df5-3be8-4a9f-169e2a10f205",
  "manufacture": "Dell Inc.",
  "product_name": "PowerEdge R740",
  "serial_number": "ABC123XYZ",
  "bios_version": "2.10.0",
  "bios_release_date": "2023-05-15",
  "os": "Ubuntu",
  "os_version": "24.04 LTS",
  "kernel": "6.8.0-71-generic",
  "cpu": "Intel(R) Xeon(R) Gold 6140 CPU @ 2.30GHz",
  "core_count": 36,
  "sockets": 1,
  "total_mem": 128,
  "mem_details": [
    {
      "size": "16 GB",
      "speed": "2666 MT/s",
      "manufacturer": "Samsung",
      "rank": "2"
    }
  ],
  "disk_count": 4,
  "disk_details": [
    {
      "name": "sda",
      "size": "1.82 TiB",
      "model": "SAMSUNG MZ7LH1T9",
      "usage": "45%",
      "used": "820G",
      "available": "890G"
    }
  ],
  "expansion_slots": [
    {
      "designation": "Slot1 PCIe",
      "type": "x16 PCI Express 3 x16",
      "current_usage": "In Use",
      "id": 1,
      "bus_address": "0000:18:00.0"
    }
  ],
  "network_interfaces": [
    {
      "pci_address": "01:00.0",
      "description": "Ethernet controller: Intel Corporation I350 Gigabit Network Connection"
    }
  ],
  "accelerator": [
    {
      "pci_address": "3b:00.0",
      "description": "3D controller: NVIDIA Corporation Tesla V100 PCIe 32GB"
    }
  ],
  "bmc_ip": "192.168.1.101",
  "bmc_mac": "a4:bf:01:23:45:67",
  "nic_mac": "a4:bf:01:23:45:68",
  "data_source": "api"
}
```

## Error Handling

The agent handles various error scenarios gracefully:

### Connection Errors
```
✗ Error submitting data: Connection error: [Errno 111] Connection refused
```
**Solution**: Verify the NexHub server is running and accessible.

### DNS/Network Errors
```
✗ Error submitting data: Connection error: [Errno -2] Name or service not known
```
**Solution**: Check the URL and network connectivity.

### Authentication Errors
```
✗ Error submitting data: HTTP 401 error: {"detail": "Invalid token"}
```
**Solution**: Verify your API token is correct.

### Permission Errors
```
✗ Error collecting data: Permission denied
```
**Solution**: Run the agent with sudo/root privileges.

### Exit Codes
- `0`: Success - Data collected and submitted successfully
- `1`: Failure - Error occurred (check logs for details)

## Logging

The agent logs all operations to `/var/log/overwatch-agent.log` (configurable):

```json
{
  "timestamp": "2025-12-09T10:30:00",
  "action": "submit",
  "hostname": "ubuntu-server-01",
  "status": "success",
  "server_id": 42,
  "data": { ... }
}
```

### View Recent Logs
```bash
sudo tail -f /var/log/overwatch-agent.log
```

### View Failed Submissions
```bash
sudo grep '"status": "error"' /var/log/overwatch-agent.log
```

## Troubleshooting

### Issue: Some hardware information missing

**Cause**: Commands require root privileges

**Solution**: Run with sudo
```bash
sudo python3 agent_linux.py --dry-run --url dummy --token dummy
```

### Issue: BMC information not collected

**Cause**: `ipmitool` not installed or BMC not configured

**Solution**: Install ipmitool (optional):
```bash
# Ubuntu/Debian
sudo apt-get install ipmitool

# RHEL/CentOS
sudo yum install ipmitool
```

### Issue: Duplicate servers in database

**Cause**: Old version of agent (before UUID filtering fix)

**Solution**: Update to latest version of agent_linux.py

### Issue: Network timeout

**Cause**: Firewall or network issues

**Solution**: Test connectivity:
```bash
curl -v http://nexhub.example.com/api/servers/
```

## Best Practices

1. **Test First**: Always run with `--dry-run` on new systems before submitting
2. **Use Sudo**: Run with root privileges for complete hardware information
3. **Schedule Wisely**: Don't run too frequently (hourly or daily is sufficient)
4. **Monitor Logs**: Check `/var/log/overwatch-agent.log` periodically
5. **Secure Tokens**: Keep API tokens secure, use environment variables or config files
6. **Version Control**: Track which version of the agent is deployed on each system

## Security Considerations

- **Token Security**: Store tokens securely, never commit to version control
- **Log Rotation**: Configure logrotate for `/var/log/overwatch-agent.log`
- **Privileges**: Agent requires root for dmidecode and other hardware commands
- **Network**: Use HTTPS URLs in production (e.g., https://nexhub.example.com)
- **Firewall**: Ensure outbound HTTPS/HTTP access to NexHub server

## Example Deployment Script

```bash
#!/bin/bash
# deploy-agent.sh - Deploy NexHub agent to multiple servers

NEXHUB_URL="http://nexhub.example.com"
NEXHUB_TOKEN="your-api-token-here"
SERVERS="server1 server2 server3"

for server in $SERVERS; do
    echo "Deploying to $server..."
    
    # Copy agent
    scp agent_linux.py root@$server:/usr/local/bin/agent_linux.py
    
    # Make executable
    ssh root@$server "chmod +x /usr/local/bin/agent_linux.py"
    
    # Test dry-run
    ssh root@$server "python3 /usr/local/bin/agent_linux.py --dry-run --url dummy --token dummy"
    
    # Add to cron
    ssh root@$server "echo '0 * * * * /usr/bin/python3 /usr/local/bin/agent_linux.py --url $NEXHUB_URL --token $NEXHUB_TOKEN' | crontab -"
    
    echo "✓ Deployed to $server"
done
```

## Support

For issues, questions, or contributions:
- GitHub: https://github.com/hong710/nexhub
- Documentation: See main README.md in the repository

## License

Same as NexHub project.
