# Overwatch Agent for Linux

A lightweight, zero-dependency system information collector for Linux servers that automatically populates the Overwatch inventory database via a simple HTTP push API.

## Design Philosophy

This agent implements an **ultra-simple, internal-only** design optimized for deployment at scale (100+ servers):

- **Single shared API key** - No per-agent registration or key rotation
- **Three files only** - agent script, config file, runner wrapper
- **No dependencies** - Pure Python 3 standard library, no external packages
- **Cron-controlled** - Simple cron job scheduling, no daemon process
- **Base64 config** - API key stored encoded (reversible, not cryptographic)
- **Bearer token auth** - Standard HTTP Authorization header

## Quick Start

### 1. Install Agent Files

On the **Overwatch server** (development/testing):

```bash
# Copy agent script to deployment location
cp agent/agent_linux.py /tmp/agent_linux.py

# Copy config template and create actual config
cp agent/etc_overwatch_config.cfg.example /tmp/config.cfg

# Edit config with your endpoint and API key
nano /tmp/config.cfg
```

### 2. Deploy to Target Servers

For a single server:

```bash
# SCP agent files to target server
ssh root@target-server << 'EOF'
mkdir -p /etc/overwatch
mkdir -p /var/log/overwatch
chmod 750 /etc/overwatch
chmod 755 /var/log/overwatch
EOF

scp /tmp/agent_linux.py root@target-server:/etc/overwatch/
scp /tmp/config.cfg root@target-server:/etc/overwatch/
scp agent/overwatch-runner root@target-server:/usr/local/bin/
chmod +x root@target-server:/usr/local/bin/overwatch-runner
```

For **bulk deployment** (100+ servers), use the provided script:

```bash
agent/tools/deploy_nexhub_agents.sh -f agent/tools/servers.txt -u https://nexhub.example.com

# servers.txt format:
# root@server1.example.com
# root@server2.example.com
# ...
```

### 3. Configure Cron

On each target server, add to root's crontab:

```bash
# Run agent hourly
0 * * * * /usr/local/bin/overwatch-runner

# Or run every 30 minutes
*/30 * * * * /usr/local/bin/overwatch-runner

# Run with dry-run for testing (outputs to /var/log/overwatch/agent_payload.json)
0 * * * * /usr/local/bin/overwatch-runner --dry-run
```

## Configuration

### /etc/overwatch/config.cfg

Configuration file read by `overwatch-runner` wrapper script:

```ini
# Overwatch server endpoint (HTTPS recommended for production)
ENDPOINT=https://nexhub.example.com

# Shared API key (base64 encoded)
# Generate with: echo -n "your-api-key-here" | base64
API_KEY_ENCODED=dGVzdC1zaGFyZWQta2V5LTE3NjU1OTUyMDU=
```

### Generating Base64-Encoded API Key

The API key is base64-encoded in the config file to prevent casual exposure. This is **not cryptographic protection** (internal-only assumption).

```bash
# Encode a key
echo -n "test-shared-key-1765595205" | base64
# Output: dGVzdC1zaGFyZWQta2V5LTE3NjU1OTUyMDU=

# Decode to verify
echo "dGVzdC1zaGFyZWQta2V5LTE3NjU1OTUyMDU=" | base64 -d
# Output: test-shared-key-1765595205
```

## Usage

### Normal Operation

Run agent to collect and submit system data:

```bash
/usr/local/bin/overwatch-runner
```

Agent collects:
- Hostname, UUID, IP address
- BMC/IPMI address (if available)
- OS name and version
- Kernel version
- CPU model, core count, sockets
- Memory size and DIMM details
- Physical disk count and model
- Network interfaces (MACs)
- PCI expansion slots
- GPU/Accelerator devices
- Device type and manufacturer

Data is submitted via HTTP POST to `/overwatch/api/agent/data/` endpoint with Bearer token authentication.

### Dry-Run Mode

Test data collection without submitting to API:

```bash
/usr/local/bin/overwatch-runner --dry-run
```

Output includes:
- Formatted summary of collected data printed to console
- Full JSON payload saved to `/var/log/overwatch/agent_payload.json`
- No HTTP request sent to Overwatch server

### Direct Agent Invocation

For testing or custom integration:

```bash
python3 /etc/overwatch/agent_linux.py \
  --url https://nexhub.example.com \
  --api-key test-shared-key-1765595205 \
  --dry-run \
  --verbose
```

## Files

### agent_linux.py

Main agent script that collects system information. Reads hardware details from:
- `/proc/cpuinfo`
- `/proc/meminfo`
- `dmidecode` (requires root)
- `ipmitool` (optional, for BMC info)
- Network interfaces via `ip` command

### /usr/local/bin/overwatch-runner

Bash wrapper script that:
1. Reads `/etc/overwatch/config.cfg`
2. Base64-decodes the API_KEY_ENCODED
3. Executes `agent_linux.py` with correct parameters
4. Supports `--dry-run` flag
5. Logs execution to `/var/log/overwatch/overwatch-runner.log`

### /etc/overwatch/config.cfg

Configuration file deployed to each target server containing:
- API endpoint URL
- Base64-encoded shared API key

## Logging

Logs are written in JSONL (JSON Lines) format for easy parsing and analysis.

### Agent Log: /var/log/overwatch-agent.log

Each line is a JSON record:

```json
{
  "timestamp": "2024-01-15T10:30:45.123456",
  "action": "collect",
  "hostname": "server01.example.com",
  "status": "success",
  "data": { ... full system data ... }
}
```

```json
{
  "timestamp": "2024-01-15T10:30:47.654321",
  "action": "submit",
  "hostname": "server01.example.com",
  "status": "success",
  "server_id": 42,
  "result": { "status": "ok", "server_id": 42 }
}
```

### Runner Log: /var/log/overwatch/overwatch-runner.log

Wrapper script execution log:

```
2024-01-15 10:30:45 [INFO] Starting overwatch-runner
2024-01-15 10:30:45 [INFO] Loaded config from /etc/overwatch/config.cfg
2024-01-15 10:30:47 [INFO] Agent completed successfully (exit code 0)
2024-01-15 10:30:47 [INFO] overwatch-runner completed
```

### Payload Inspection: /var/log/overwatch/agent_payload.json

When running in `--dry-run` mode, the full collected data is saved here for inspection:

```bash
# View the payload that would be submitted
cat /var/log/overwatch/agent_payload.json | jq .

# Useful for troubleshooting collection issues
cat /var/log/overwatch/agent_payload.json | jq '.cpu'
```

## Troubleshooting

### Check if agent is running via cron

View recent cron execution logs:

```bash
# On systemd systems
journalctl -u cron -n 20

# Check /var/log/overwatch/ for agent logs
tail -20 /var/log/overwatch/overwatch-runner.log
tail -20 /var/log/overwatch-agent.log
```

### Verify configuration

```bash
# Check config file is readable
cat /etc/overwatch/config.cfg

# Verify base64 encoding of API key
grep API_KEY_ENCODED /etc/overwatch/config.cfg | \
  awk -F= '{print $2}' | base64 -d
```

### Test dry-run locally

```bash
# Run in dry-run mode to see collected data
/usr/local/bin/overwatch-runner --dry-run

# View collected payload
cat /var/log/overwatch/agent_payload.json | jq .
```

### Test with verbose output

```bash
# Run agent directly with verbose flag
python3 /etc/overwatch/agent_linux.py \
  --url https://nexhub.example.com \
  --api-key test-shared-key-1765595205 \
  --verbose
```

### Check API connectivity

```bash
# Test if endpoint is reachable
curl -v https://nexhub.example.com/overwatch/api/agent/data/ \
  -H "Authorization: Bearer test-shared-key-1765595205" \
  -H "Content-Type: application/json" \
  -d '{"hostname": "test"}'
```

### Verify server was registered

On Overwatch server:

```bash
# Check if hostname appears in inventory
curl -H "Authorization: Token YOUR_REST_API_TOKEN" \
  http://localhost:8000/api/servers/?hostname=target-server.example.com

# Or use Django shell
python manage.py shell
>>> from overwatch.models import Server
>>> Server.objects.filter(hostname='target-server.example.com').first()
```

### Permission issues

```bash
# Ensure directories are writable
ls -la /etc/overwatch/
ls -la /var/log/overwatch/

# Fix if needed (run on target server)
sudo chown root:root /etc/overwatch
sudo chmod 750 /etc/overwatch
sudo chown root:root /var/log/overwatch
sudo chmod 755 /var/log/overwatch
```

## Security Considerations

### Internal-Only Design

This agent is designed for **internal networks only**:
- Single shared API key (no per-agent identity)
- Base64 encoding for config (not cryptographic)
- No certificate validation (adjust in production)
- No request signing or HMAC verification

For production/untrusted networks:
- Use HTTPS only (configured in agent URL)
- Implement per-agent API key model (see Agent model in codebase)
- Add request signing/HMAC validation
- Implement IP whitelisting at firewall
- Use VPN/private network for agent communication

### API Key Management

The shared API key is stored in `/etc/overwatch/config.cfg` on each server:

```bash
# Rotate key if compromised
# 1. Update AGENT_API_KEY in Django settings.py
# 2. Re-deploy config.cfg to all servers with new base64-encoded key
# 3. Optionally: restart cron jobs or wait for next scheduled execution

# View all servers' config version (via SSH)
for host in $(cat /tmp/servers.txt); do
  echo "=== $host ==="
  ssh $host grep API_KEY_ENCODED /etc/overwatch/config.cfg
done
```

## API Reference

### POST /overwatch/api/agent/data/

Minimal agent push endpoint.

**Authentication:** Bearer token in Authorization header

```bash
curl -X POST https://nexhub.example.com/overwatch/api/agent/data/ \
  -H "Authorization: Bearer test-shared-key-1765595205" \
  -H "Content-Type: application/json" \
  -d '{
    "hostname": "server01.example.com",
    "uuid": "550e8400-e29b-41d4-a716-446655440000",
    "ip_address": "192.168.1.10",
    "bmc_ip": "192.168.1.11",
    "nic_mac": "00:11:22:33:44:55",
    "os": "Ubuntu",
    "os_version": "22.04 LTS",
    "kernel": "5.15.0-56-generic",
    "cpu": "Intel(R) Xeon(R) CPU E5-2699 v4 @ 2.20GHz",
    "core_count": 22,
    "sockets": 2,
    "total_mem": 256,
    "disk_count": 4,
    "device_type": "server",
    "manufacture": "Dell Inc.",
    "product_name": "PowerEdge R730"
  }'
```

**Request Fields:**
- `hostname` (required) - Server hostname
- `uuid` (optional) - System UUID (auto-generated if missing)
- `ip_address` (optional) - Primary IP address
- `bmc_ip` (optional) - Out-of-band management IP
- `nic_mac` (optional) - MAC address of primary NIC
- `os` (optional) - Operating system name
- `os_version` (optional) - OS version string
- `kernel` (optional) - Kernel version
- `cpu` (optional) - CPU model string
- `core_count` (optional) - Number of CPU cores
- `sockets` (optional) - Number of CPU sockets
- `total_mem` (optional) - Memory in GB
- `disk_count` (optional) - Number of physical disks
- `device_type` (optional) - Device type (server, switch, etc.)
- `manufacture` (optional) - Equipment manufacturer
- `product_name` (optional) - Product model name

**Response (Success 200):**
```json
{
  "status": "ok",
  "server_id": 42
}
```

**Response (Unauthorized 401):**
```json
{
  "detail": "Invalid API key"
}
```

**Response (Bad Request 400):**
```json
{
  "detail": "Invalid JSON payload"
}
```

## Advanced Integration

### Custom Data Collection

Extend `SystemCollector` class in `agent_linux.py` to gather additional data:

```python
class SystemCollector:
    # Add custom collection methods
    def collect_custom_metric(self):
        # Your custom logic
        return value
    
    def collect_all(self):
        # ... existing collections ...
        data['custom_metric'] = self.collect_custom_metric()
        return data
```

### Custom Configuration File

Override default config location:

```bash
/usr/local/bin/overwatch-runner --config /opt/custom/config.cfg
```

### Integrated Error Handling

Agent logs all errors to `/var/log/overwatch-agent.log` in JSON format:

```bash
# View only errors
grep '"status": "error"' /var/log/overwatch-agent.log | jq .

# View last 10 errors with details
grep '"status": "error"' /var/log/overwatch-agent.log | tail -10 | jq .error
```

## Performance

Typical execution times:
- **Collection:** 1-3 seconds (dmidecode slowest on large systems)
- **Submit:** 0.5-1 second (network dependent)
- **Total:** 2-5 seconds per execution

For 100+ servers on hourly schedule:
- CPU impact: Negligible
- Network: ~5-50 KB per request (~100 KB total for 100 servers/hour)
- Disk: ~1 KB log per request (rotate logs regularly)

## Support

For issues or questions:

1. Check logs in `/var/log/overwatch/`
2. Run `--dry-run` to verify data collection
3. Test API endpoint with curl
4. Check Django admin interface for registered servers
5. Review Django error logs: `/var/log/django/`

## License

Same as main Overwatch project
