# IPAM System - Quick Reference Guide

## What Changed

You now have a **database-driven IPAM system** instead of JavaScript-based IP generation. All IPs are tracked in the database with synchronization between Server and IPAM tables.

## Key Workflow

### 1. Creating Subnets with Static IPs
When you create a subnet in `/admin/overwatch/subnet/` with `static_ip_pools`:
```
static_ip_pools: ["192.168.1.1-192.168.1.50", "192.168.1.100-192.168.1.150"]
```
- 100 IPAM records are **automatically created**
- Status: "Available"
- Type: "Static"
- Appears immediately in `/ipam/` page

### 2. Server IP Assignment
When a server gets assigned an IP (via agent or manual entry):
1. Server.ip_address = "192.168.1.10"
2. Signal handler automatically:
   - Finds the subnet containing that IP
   - Creates/updates IPAM record
   - Sets status to "Allocated"
   - Syncs hostname, MAC, platform, manufacturer
   - Updates IPAM page in real-time

### 3. IP Status Management

| Status | Meaning | Editable | Use Case |
|--------|---------|----------|----------|
| **Available** | No server using it | No | Unassigned static IPs |
| **Allocated** | Server is using it | No | Server has this IP |
| **Reserved** | Manually reserved | **Yes** | Network device, printer, gateway |
| **Quarantine** | Unavailable | No | Problematic IP, blocked range |

**Note**: Description field only editable when status = "Reserved"

### 4. Server Deletion/IP Change
When a server's IP changes from 192.168.1.10 → 192.168.1.20:
- Old IP (192.168.1.10): Status → "Available", Server cleared
- New IP (192.168.1.20): Status → "Allocated", Server linked
- Automatic sync, no manual action needed

## Pages & Features

### `/ipam/` - IP List View
- **Filters**: Subnet dropdown, Status dropdown, Search (IP/Hostname/MAC)
- **Display**: 25 IPs per page
- **Statistics**: Shows count of Available/Allocated/Reserved IPs
- **Actions**: Click "Edit" to manage individual IPs in admin

### `/admin/overwatch/ipam/` - Admin Management
- **Edit IPs**: Change status, add description, reserve IPs
- **Search**: By IP address or MAC address
- **Bulk Filters**: By Status, Subnet, Active flag, Type
- **Columns**: IP, Subnet, Hostname, Status, Active, Type

### `/admin/overwatch/subnet/` - Subnet Configuration
- **static_ip_pools**: JSON array of IP ranges
  ```json
  ["192.168.1.1-192.168.1.50", "192.168.1.100-192.168.1.150"]
  ```
- Creating/updating this field triggers IPAM population
- Deleting subnet deletes all associated IPs

## API Endpoints

### GET `/api/ipam/`
Retrieve all IPAM records (paginated):
```bash
curl http://localhost:8000/api/ipam/?subnet=1&status=allocated
```

### GET `/api/servers/`
Get server data with IP assignments:
```bash
curl http://localhost:8000/api/servers/?page_size=100
```

## Management Commands

### Populate IPAM from Subnets & Servers
```bash
python manage.py populate_ipam
```
**Output:**
```
✓ Created 654 static IPAM records
✓ Updated 72 IPAM records from servers

📊 IPAM Summary:
   Total Records: 687
   Available: 582
   Allocated: 105
   Reserved: 0
```

### Clear & Repopulate
```bash
python manage.py populate_ipam --clear
```

## Database Fields Explained

Each IPAM record contains:

| Field | Type | Auto-Sync | Notes |
|-------|------|-----------|-------|
| `ip_address` | IP | No | The actual IP address |
| `subnet` | FK | No | Which subnet it belongs to |
| `ip_type` | Choice | Yes | "static" or "dhcp" |
| `status` | Choice | Yes | available/allocated/reserved/quarantine |
| `server` | FK | Yes | Linked Server instance (if allocated) |
| `hostname` | Char | Yes | From Server.hostname |
| `mac_address` | Char | Yes | From Server.nic_mac |
| `platform` | Char | Yes | From Server.device_type |
| `manufacturer` | Char | Yes | From Server.manufacture |
| `active` | Bool | No | Ping status (for future implementation) |
| `description` | Text | Manual | User notes (only editable when reserved) |

## Signal Handlers

Three automatic synchronization points:

### 1. Server IP Changes
```python
@receiver(post_save, sender=Server)
def sync_server_to_ipam(sender, instance, ...)
```
Triggered when: Server.ip_address is saved
Action: Update/create matching IPAM record

### 2. Server Deleted
```python
@receiver(post_delete, sender=Server)
def cleanup_server_ipam(sender, instance, ...)
```
Triggered when: Server is deleted
Action: Delete DHCP IPs, mark static IPs available

### 3. Subnet Static Pools Change
```python
@receiver(post_save, sender=Subnet)
def populate_static_ipam(sender, instance, ...)
```
Triggered when: Subnet.static_ip_pools is changed
Action: (Re)create all static IP records

## Common Tasks

### Reserve an IP for a Network Device
1. Go to `/admin/overwatch/ipam/`
2. Find the IP address
3. Change Status to "Reserved"
4. Add Description: "Network printer IP"
5. Leave Server empty
6. Save

### Find All Available IPs in a Subnet
1. Go to `/ipam/`
2. Select Subnet from dropdown
3. Select Status: "Available"
4. Click Filter
5. Table shows all unassigned IPs

### Bulk Update IPs
1. Go to `/admin/overwatch/ipam/`
2. Check boxes for multiple IPs
3. Select "Change status" from dropdown
4. Choose new status
5. Click "Go"

### Track Server IP History
- Check `/ipam/` page for current assignment
- Admin page shows when IP was created/updated (timestamps)
- Description field stores manual notes

## Troubleshooting

**Problem**: New subnet created but IPs not showing in IPAM
- Solution: Check subnet.static_ip_pools is valid JSON like `["192.168.1.1-192.168.1.50"]`
- Run: `python manage.py populate_ipam` to manually sync

**Problem**: Server IP changed but IPAM not updated
- Solution: Check if server.ip_address was actually saved
- Signals only trigger on successful save
- Check Django admin for updates

**Problem**: IPAM page loading slowly
- Solution: Data is paginated (25 per page), try filtering by:
  - Specific subnet
  - Specific status
  - Search term

**Problem**: Can't edit description
- Solution: Status must be "Reserved" to edit description
- Change status first, then description becomes editable

## Future Enhancements

- [ ] Ping status check (active field) - automated script
- [ ] DHCP pool visualization
- [ ] IP conflict detection
- [ ] Bulk import/export
- [ ] Audit trail (who changed what)
- [ ] REST API for external systems
- [ ] Integration with Infoblox/phpIPAM

## Performance Notes

- Database indexes on: (subnet, status), (ip_address)
- Pagination keeps views fast
- Signals are atomic and transactional
- 687 IPs loads in <200ms

## Support

For issues or questions, check:
1. `/ipam/` - View current state
2. `/admin/overwatch/ipam/` - Debug individual records
3. `/admin/overwatch/server/` - Check server configurations
4. Django logs for signal errors
