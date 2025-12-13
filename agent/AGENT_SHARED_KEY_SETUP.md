# NexHub Agent - Shared Key Setup Guide

Quick reference for deploying the NexHub agent with a single shared API key (internal-only security model).

## Architecture

```
┌─────────────────────────────────────────────────────────────┐
│                        NexHub Server                        │
│  ┌────────────────────────────────────────────────────┐    │
│  │  settings.py: AGENT_API_KEY = "secret-key-123"     │    │
│  └────────────────────────────────────────────────────┘    │
│  ┌────────────────────────────────────────────────────┐    │
│  │  POST /overwatch/api/agent/data/                   │    │
│  │  • Check "Authorization: Bearer <key>" header      │    │
│  │  • Compare to settings.AGENT_API_KEY               │    │
│  │  • Return 401 if mismatch                          │    │
│  │  • Upsert Server (uuid→nic_mac→ip→hostname)       │    │
│  └────────────────────────────────────────────────────┘    │
└─────────────────────────────────────────────────────────────┘
                              ▲
                              │ HTTPS + Bearer Token
                              │
         ┌────────────────────┼────────────────────┐
         │                    │                    │
    ┌────▼─────┐         ┌───▼──────┐        ┌───▼──────┐
    │ Server 1 │         │ Server 2 │  ...   │ Server N │
    ├──────────┤         ├──────────┤        ├──────────┤
    │ agent.py │         │ agent.py │        │ agent.py │
    │   +      │         │   +      │        │   +      │
    │ agent.key│         │ agent.key│        │ agent.key│
    │ (600)    │         │ (600)    │        │ (600)    │
    └──────────┘         └──────────┘        └──────────┘
    Same key on all servers: "secret-key-123"
```

## Server-Side Setup

**1. Configure shared key** in [nexhub/settings.py](nexhub/settings.py):

```python
# Around line 21, after ALLOWED_HOSTS
AGENT_API_KEY = "change-this-to-a-strong-secret-key-123"
```

**Security tip:** Generate a strong random key:
```bash
python3 -c "import secrets; print(secrets.token_urlsafe(32))"
```

**2. Restart Django** to load the new setting:
```bash
# Development
.venv/bin/python manage.py runserver

# Production (systemd example)
sudo systemctl restart nexhub
```

## Client-Side Setup

### Single Server (Manual)

```bash
# 1. Copy agent script
scp agent_linux.py user@target:/tmp/
ssh user@target 'sudo mv /tmp/agent_linux.py /usr/local/bin/ && sudo chmod +x /usr/local/bin/agent_linux.py'

# 2. Store shared key (REPLACE WITH YOUR KEY!)
ssh user@target "echo 'change-this-to-a-strong-secret-key-123' | sudo tee /etc/nexhub/agent.key >/dev/null && sudo chmod 600 /etc/nexhub/agent.key"

# 3. Install cron (hourly)
ssh user@target "echo '0 * * * * /usr/bin/python3 /usr/local/bin/agent_linux.py --url https://nexhub.example.com --api-key \$(cat /etc/nexhub/agent.key) >> /var/log/nexhub-agent-cron.log 2>&1' | sudo crontab -"

# 4. Test immediately
ssh user@target "/usr/bin/python3 /usr/local/bin/agent_linux.py --url https://nexhub.example.com --api-key \$(cat /etc/nexhub/agent.key)"
```

### Bulk Deployment (100+ Servers)

**1. Create inventory file:**
```bash
cat > agent/tools/servers.txt <<EOF
server1.example.com
user@server2.example.com
10.0.0.50
# Comments allowed
192.168.1.100
EOF
```

**2. Export shared key and deploy:**
```bash
export AGENT_API_KEY="change-this-to-a-strong-secret-key-123"
agent/tools/deploy_nexhub_agents.sh -f agent/tools/servers.txt -u https://nexhub.example.com
```

**3. Verify deployment:**
```bash
# Check cron job
ssh server1.example.com 'sudo crontab -l | grep agent_linux'

# Check key file
ssh server1.example.com 'sudo ls -la /etc/nexhub/agent.key'

# Check logs
ssh server1.example.com 'sudo tail /var/log/nexhub-agent-cron.log'
```

## Testing

### Local Test (Before Deployment)

```bash
# Dry run (no API call)
sudo python3 agent_linux.py --dry-run --url dummy --api-key dummy

# Real submission (local dev server)
python3 agent_linux.py --url http://127.0.0.1:8000 --api-key "your-test-key"
```

### Verify Authentication

**Valid key (should succeed):**
```bash
curl -X POST https://nexhub.example.com/overwatch/api/agent/data/ \
  -H "Authorization: Bearer your-strong-secret-key-123" \
  -H "Content-Type: application/json" \
  -d '{"hostname":"test","uuid":"00000000-0000-0000-0000-000000000001"}'
```

**Invalid key (should return 401):**
```bash
curl -X POST https://nexhub.example.com/overwatch/api/agent/data/ \
  -H "Authorization: Bearer wrong-key" \
  -H "Content-Type: application/json" \
  -d '{"hostname":"test","uuid":"00000000-0000-0000-0000-000000000001"}'
# Expected: {"detail": "Invalid API key"}
```

## Server Matching Logic

When an agent submits data, NexHub matches/creates servers using this cascade:

1. **UUID** (preferred): Unique hardware identifier from DMI
2. **NIC MAC**: First non-loopback MAC address (unique constraint)
3. **IP Address**: Primary IP (unique constraint)
4. **Hostname**: System hostname (unique constraint)
5. **Auto-UUID**: Generate new UUID if all above fail (prevents duplicates)

This ensures:
- Hardware replacements (same UUID) update the correct record
- Hostname changes don't create duplicates (matches on UUID/MAC)
- Multiple servers with same hostname are handled (matches on UUID/MAC/IP first)

## Security Notes

### Internal-Only Model
- ✅ Simple: One key for all agents
- ✅ Easy deployment: Same key everywhere
- ✅ No rotation complexity
- ❌ No per-agent identity
- ❌ No per-agent revocation
- ❌ Key compromise affects all agents

### Best Practices
1. **Use HTTPS** - Key is sent in header, protect it in transit
2. **File permissions** - `/etc/nexhub/agent.key` must be mode 600 (root only)
3. **Network isolation** - Internal network only, firewall from internet
4. **Key rotation** - Change key periodically, redeploy to all servers
5. **Log monitoring** - Watch for 401 errors (indicates key mismatch or attack)

### When to Use Per-Agent Keys Instead
Consider switching to per-agent keys if:
- Multi-tenant environment (different customers)
- External-facing agents (over internet)
- Need per-agent revocation (without affecting others)
- Compliance requires audit trail of which agent did what
- High-security environment

## Troubleshooting

### Agent Returns 401 Unauthorized

**Causes:**
- Key mismatch between `/etc/nexhub/agent.key` and `settings.AGENT_API_KEY`
- Key file not readable by cron user (permissions issue)
- Server settings not reloaded after key change

**Fix:**
```bash
# On target: verify key file
ssh target 'sudo cat /etc/nexhub/agent.key'

# On NexHub server: verify settings
grep AGENT_API_KEY nexhub/settings.py

# Match? Restart NexHub server
sudo systemctl restart nexhub
```

### Agent Not Running

**Check cron:**
```bash
sudo crontab -l | grep agent_linux
```

**Check logs:**
```bash
sudo tail -50 /var/log/nexhub-agent-cron.log
```

**Manual test:**
```bash
sudo /usr/bin/python3 /usr/local/bin/agent_linux.py \
  --url https://nexhub.example.com \
  --api-key $(cat /etc/nexhub/agent.key) \
  --verbose
```

### Duplicate Servers Created

**Issue:** Multiple entries for same physical server

**Causes:**
- UUID collection failing (returns null/empty)
- MAC address changing (virtualization, network config)
- All unique fields (UUID, MAC, IP, hostname) changed simultaneously

**Fix:**
1. Check UUID collection: `sudo dmidecode -s system-uuid`
2. Verify MAC stability: `ip link show`
3. Manually merge duplicates in Django admin
4. Set static MAC or use UUID pinning

## Files Modified

### Server-Side
- [nexhub/settings.py](nexhub/settings.py) - Added `AGENT_API_KEY` setting
- [overwatch/views.py](overwatch/views.py) - Updated `agent_data_push()` to validate Bearer token
- [overwatch/models.py](overwatch/models.py) - Removed `Agent` model (was per-agent keys)
- [overwatch/migrations/0021_remove_agent_model.py](overwatch/migrations/0021_remove_agent_model.py) - Drop `Agent` table
- `overwatch/management/commands/create_agent.py` - Deleted (no longer needed)
- `overwatch/management/commands/revoke_agent.py` - Deleted (no longer needed)

### Client-Side
- [agent_linux.py](agent_linux.py) - Sends `Authorization: Bearer <key>` header
- [agent/tools/deploy_nexhub_agents.sh](agent/tools/deploy_nexhub_agents.sh) - Simplified to write shared key

### Documentation
- [README.md](README.md) - Updated Agent Push API section
- [README_AGENT.md](README_AGENT.md) - Updated authentication and cron sections
- This file - Quick reference guide

## Quick Commands Reference

```bash
# Generate strong key
python3 -c "import secrets; print(secrets.token_urlsafe(32))"

# Update server settings
sed -i 's/AGENT_API_KEY = .*/AGENT_API_KEY = "NEW_KEY"/' nexhub/settings.py

# Deploy to single server
export TARGET="server.example.com"
export NEXHUB_URL="https://nexhub.example.com"
export KEY="your-key-here"
scp agent_linux.py $TARGET:/tmp/ && \
ssh $TARGET "sudo mv /tmp/agent_linux.py /usr/local/bin/ && sudo chmod +x /usr/local/bin/agent_linux.py && echo '$KEY' | sudo tee /etc/nexhub/agent.key >/dev/null && sudo chmod 600 /etc/nexhub/agent.key && echo '0 * * * * /usr/bin/python3 /usr/local/bin/agent_linux.py --url $NEXHUB_URL --api-key \$(cat /etc/nexhub/agent.key) >> /var/log/nexhub-agent-cron.log 2>&1' | sudo crontab -"

# Bulk deploy
export AGENT_API_KEY="your-key-here"
agent/tools/deploy_nexhub_agents.sh -f agent/tools/servers.txt -u https://nexhub.example.com

# Test authentication
curl -X POST https://nexhub.example.com/overwatch/api/agent/data/ \
  -H "Authorization: Bearer your-key-here" \
  -H "Content-Type: application/json" \
  -d '{"hostname":"test","uuid":"test-uuid-123"}'

# Check Django logs (systemd)
sudo journalctl -u nexhub -f

# Verify server was created
python manage.py shell -c "from overwatch.models import Server; print(Server.objects.filter(data_source='api').count(), 'agent-submitted servers')"
```

## Migration from Per-Agent Keys (If Upgrading)

If you previously used the `Agent` model with per-agent keys:

**1. Export existing hostnames:**
```bash
python manage.py shell -c "from overwatch.models import Agent; print('\n'.join(Agent.objects.values_list('hostname', flat=True)))" > old_agents.txt
```

**2. Generate new shared key and update settings.py**

**3. Redeploy to all hosts:**
```bash
export AGENT_API_KEY="new-shared-key"
agent/tools/deploy_nexhub_agents.sh -f old_agents.txt -u https://nexhub.example.com
```

**4. Verify servers still reporting:**
```bash
python manage.py shell -c "from overwatch.models import Server; from django.utils import timezone; from datetime import timedelta; recent = Server.objects.filter(updated_at__gte=timezone.now()-timedelta(hours=2)); print(recent.count(), 'servers updated in last 2 hours')"
```

**5. Remove old Agent model** (already done in migration 0021)
