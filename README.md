# NexHub

**NexHub** is a Django-based infrastructure management platform for tracking and managing servers, networks, subnets, and related IT assets.

## Features

### Server Management (Overwatch Module)
- **Server Inventory**: Track servers with detailed specifications including CPU, memory, storage, PDU information
- **Network Configuration**: IP addresses, MAC addresses, BMC details
- **Categorization**: Organize servers by categories
- **Tagging System**: Flexible tagging for better organization
- **Notes System**: Add timestamped notes to servers
- **Professional UI**: Modern, responsive interface with Tailwind CSS + Flowbite

### Subnet Management
- **Network Planning**: CIDR notation support with automatic calculations
- **VLAN Support**: Associate subnets with VLAN IDs
- **IP Pool Management**: 
  - Static IP Pool configuration with dynamic From/To inputs
  - Auto-calculated DHCP pools from remaining IPs
  - Visual IP allocation tracking with percentage bars
- **Usage Statistics**: Usable IPs, Available IPs, allocation metrics
- **Detail View**: Tag-style display for IP blocks

### Data Management
- **Data Dictionary**: Translate between different naming conventions
- **Tags**: Flexible tagging system with color coding
- **Categories**: Organize servers into logical categories

## Technology Stack

- **Backend**: Django 6.0 (Python 3.12)
- **Frontend**: 
  - Tailwind CSS v3.4.17
  - Flowbite 2.2.1 (UI components)
  - HTMX (dynamic interactions)
- **Database**: SQLite (development) / PostgreSQL-ready

## Database Schema (ERD)

### Core Models

```
┌─────────────────────┐         ┌──────────────────┐
│      Server         │         │    Category      │
├─────────────────────┤         ├──────────────────┤
│ id (PK)            │◄───────┤│ id (PK)         │
│ category_id (FK)   │         ││ name            │
│ hostname           │         ││ description     │
│ uuid               │         ││ created_at      │
│ ip_address         │         ││ updated_at      │
│ bmc_ip             │         │└──────────────────┘
│ nic_mac            │         │
│ bmc_mac            │         │
│ manufacture        │         │
│ product_name       │         │
│ cpu                │         │
│ core_count         │         │
│ sockets            │         │
│ memory_gb          │         │
│ storage_type       │         │
│ storage_capacity_gb│         │
│ pdu1_port          │         │
│ pdu1_ip            │         │
│ pdu2_port          │         ┌──────────────────┐
│ pdu2_ip            │         │       Tag        │
│ info               │         ├──────────────────┤
│ priority           │         │ id (PK)         │
│ created_at         │         │ name            │
│ updated_at         │         │ color           │
└─────────────────────┘         │ description     │
         │                      │ server_id (FK) │
         │ 1:N                  │ created_at     │
         ▼                      │ updated_at     │
┌─────────────────────┐         └──────────────────┘
│    ServerNote       │                  ▲
├─────────────────────┤                  │ M:N
│ id (PK)            │                  │
│ server_id (FK)     │         ┌────────┴──────────┐
│ note               │         │   Server_Tags     │
│ created_at         │         ├───────────────────┤
│ updated_at         │         │ server_id (FK)   │
└─────────────────────┘         │ tag_id (FK)      │
                                └───────────────────┘

┌─────────────────────┐         ┌──────────────────────┐
│      Subnet         │         │  DataDictionary     │
├─────────────────────┤         ├──────────────────────┤
│ id (PK)            │         │ id (PK)             │
│ name               │         │ standard_term       │
│ network            │         │ source_term         │
│ vlan_id            │         │ translate_from      │
│ gateway            │         │ description         │
│ description        │         │ created_at          │
│ static_ip_pools    │         │ updated_at          │
│ dhcp_pools         │         └──────────────────────┘
│ created_at         │
│ updated_at         │
└─────────────────────┘
```

### Key Relationships
- **Server ↔ Category**: Many-to-One (servers belong to one category)
- **Server ↔ Tag**: Many-to-Many (servers can have multiple tags)
- **Server ↔ ServerNote**: One-to-Many (servers can have multiple notes)
- **Subnet**: Independent entity with JSON fields for IP pool storage

### Field Descriptions

#### Server
- **Network Info**: `ip_address`, `bmc_ip`, `nic_mac`, `bmc_mac`
- **Hardware**: `cpu`, `core_count`, `sockets`, `memory_gb`, `storage_type`, `storage_capacity_gb`
- **PDU**: `pdu1_port`, `pdu1_ip`, `pdu2_port`, `pdu2_ip` (Power Distribution Unit connections)
- **Metadata**: `info` (JSONField), `priority` (integer), timestamps

#### Subnet
- **Network**: `network` (CIDR notation, e.g., 192.168.1.0/24)
- **IP Pools**: 
  - `static_ip_pools` (JSONField): Array of IP ranges as strings ["10.0.1.1-10.0.1.50"]
  - `dhcp_pools` (JSONField): Auto-calculated from network minus static pools
- **VLAN**: `vlan_id` (1-4094)
- **Gateway**: `gateway` (optional)

#### Tag
- **Visual**: `color` field for UI customization
- **Relationship**: Links to servers through many-to-many relationship

#### DataDictionary
- **Translation**: Maps `source_term` to `standard_term`
- **Context**: `translate_from` indicates source system

## Installation

```bash
# Clone the repository
git clone git@github.com:hong710/nexhub.git
cd nexhub

# Create virtual environment
python -m venv .venv
source .venv/bin/activate  # On Windows: .venv\Scripts\activate

# Install dependencies
pip install -r requirements.txt

# Run migrations
python manage.py migrate

# Collect static files (CSS, JS) - Required for production deployment
# For development, this step is optional as Django serves static files automatically
python manage.py collectstatic --noinput

# Create superuser
python manage.py createsuperuser

# Run development server
python manage.py runserver
```

## Usage

### Seed Demo Data (Optional)
```bash
python manage.py seed_demo
```

### Static Files
The project uses **local static files** instead of CDN for production readiness:
- **Tailwind CSS v3.4.17** - `/static/js/tailwind.min.js`
- **Flowbite v2.2.1** - `/static/css/flowbite.min.css` and `/static/js/flowbite.min.js`
- **HTMX v1.9.12** - `/static/js/htmx.min.js`

**How it works:**
- **Development**: Django automatically serves files from `/static/` directory
- **Production**: Run `collectstatic` to copy all static files to `/staticfiles/` for web server (Nginx/Apache) to serve
- The `staticfiles/` directory is excluded from git (generated during deployment)

### Using the Data Dictionary

The dictionary lets you normalize vendor- or source-specific terms into your own standardized labels.

1) Go to `/dictionary/` (UI) and add a row for each translation you need:
  - **Translate From**: source field name (e.g., `product_name`, `manufacture`, `cpu`, `os`).
  - **Original Keyword**: the raw value you receive (e.g., `HP`, `HPE`, `Hewlett Packard`).
  - **Standardized Value**: your normalized value (e.g., `HPE`).
  - **Is Active**: keep checked to apply.

2) How it is applied:
  - When servers are saved/ingested, the fields `product_name`, `manufacture`, `cpu`, and `os` are auto-translated if a matching active dictionary entry exists (case-insensitive match on Original Keyword for the given Translate From field).
  - Translated values are persisted back to the server record, so the normalized form is what you see and filter on.

3) Tips:
  - Enter the same standardized value for all variants you want collapsed (e.g., `Ubuntu`, `ubuntu`, `Ubuntu Server` -> `Ubuntu`).
  - Leave an entry inactive to keep it for reference without applying it.
```

### Access the Application
1. Navigate to `http://127.0.0.1:8000/`
2. Log in with your superuser credentials
3. Access modules:
   - `/` - Server list
   - `/subnets/` - Subnet management
   - `/tags/` - Tag management
   - `/categories/` - Category management
   - `/dictionary/` - Data dictionary
   - `/api/` - REST API (requires token authentication)

## REST API

NexHub provides a comprehensive REST API for programmatic access and agent-based data collection.

### API Endpoints

#### Authentication
All API endpoints require token authentication:
```bash
# Include token in Authorization header
curl -H "Authorization: Token YOUR_TOKEN_HERE" http://localhost:8000/api/servers/
```

#### Generate API Token
```bash
python manage.py shell -c "from django.contrib.auth.models import User; from rest_framework.authtoken.models import Token; user = User.objects.get(username='YOUR_USERNAME'); token, created = Token.objects.get_or_create(user=user); print(f'Token: {token.key}')"
```

#### Available Endpoints

**Servers**
- `GET /api/servers/` - List all servers
- `POST /api/servers/` - Create a server
- `GET /api/servers/{id}/` - Get server details
- `PATCH /api/servers/{id}/` - Update server
- `DELETE /api/servers/{id}/` - Delete server
- `POST /api/servers/bulk_create/` - Create multiple servers
- `POST /api/servers/{id}/update_status/` - Update server status

**Categories**
- `GET /api/categories/` - List all categories
- `POST /api/categories/` - Create a category
- `GET /api/categories/{id}/` - Get category details
- `PATCH /api/categories/{id}/` - Update category
- `DELETE /api/categories/{id}/` - Delete category

**Tags**
- `GET /api/tags/` - List all tags
- `POST /api/tags/` - Create a tag
- `GET /api/tags/{id}/` - Get tag details
- `PATCH /api/tags/{id}/` - Update tag
- `DELETE /api/tags/{id}/` - Delete tag

**Subnets**
- `GET /api/subnets/` - List all subnets
- `POST /api/subnets/` - Create a subnet
- `GET /api/subnets/{id}/` - Get subnet details
- `PATCH /api/subnets/{id}/` - Update subnet
- `DELETE /api/subnets/{id}/` - Delete subnet

### Query Parameters
- `search` - Search across relevant fields
- `ordering` - Order results (e.g., `-created_at`, `hostname`)
- `page` - Page number (default: 1)
- `page_size` - Results per page (default: 100)

### Example API Calls

**List servers:**
```bash
curl -H "Authorization: Token YOUR_TOKEN" \
     "http://localhost:8000/api/servers/?search=ubuntu&page_size=10"
```

**Create a server:**
```bash
curl -X POST -H "Authorization: Token YOUR_TOKEN" \
     -H "Content-Type: application/json" \
     -d '{"hostname": "server01", "ip_address": "192.168.1.10", "status": "active"}' \
     http://localhost:8000/api/servers/
```

**Update a server:**
```bash
curl -X PATCH -H "Authorization: Token YOUR_TOKEN" \
     -H "Content-Type: application/json" \
     -d '{"status": "maintenance"}' \
     http://localhost:8000/api/servers/1/
```

## Agent Script

NexHub includes an agent script (`agent_linux.py`) that automatically collects system information and submits it to the API.

### Agent Features
- **Zero dependencies** - Uses only Python 3 standard library (urllib)
- Collects hostname, IP address, MAC address
- Detects OS information (name, version, kernel)
- Gathers CPU details (model, core count)
- Reports memory size
- Lists disk information
- Identifies system manufacturer and model
- Updates existing servers or creates new ones

### Agent Requirements
```bash
# No external dependencies required - Python 3.6+ only!
python3 --version  # Verify Python 3.6 or higher
```

### Agent Usage

**Dry run (preview collected data without submitting to API):**
```bash
python agent_linux.py --url http://nexhub.example.com --token YOUR_TOKEN --dry-run
```

This will display a formatted summary of collected system information:
```
================================================================================
DRY RUN MODE - DATA COLLECTION PREVIEW
================================================================================

🖥️  BASIC INFO:
   Hostname:     ubuntu-hp-g2
   UUID:         8c178819-2df5-3be8-4a9f-169e2a10f205
   IP Address:   192.168.65.15
   Manufacturer: HP
   Product:      HP Elite Slice G2 MS SRS Audio Ready

💻 CPU INFO:
   Model:        Intel(R) Core(TM) i5-7500T CPU @ 2.70GHz
   Cores:        4

💾 DISK:
   Disks:        2 physical disk(s)

🌐 NETWORK INTERFACES:
   Count:        2 interface(s)

✓ Data collection successful!
  Run without --dry-run to submit this data to the API
```

**Dry run with full JSON output:**
```bash
python agent_linux.py --url http://nexhub.example.com --token YOUR_TOKEN --dry-run --verbose
```

**Submit data to API:**
```bash
python agent_linux.py --url http://nexhub.example.com --token YOUR_TOKEN
```

**Submit with verbose output:**
```bash
python agent_linux.py --url http://nexhub.example.com --token YOUR_TOKEN --verbose
```

### Agent Example Output
```json
{
  "hostname": "ubuntu-hp-g2",
  "ip_address": "192.168.65.15",
  "nic_mac": "84:3a:5b:10:ce:5f",
  "data_source": "api",
  "status": "active",
  "os": "Linux",
  "os_version": "6.8.0-71-generic",
  "kernel": "#71-Ubuntu SMP PREEMPT_DYNAMIC",
  "cpu": "Intel(R) Core(TM) i5-7500T CPU @ 2.70GHz",
  "core_count": 4,
  "total_mem": 15,
  "disk_count": 2,
  "disk_details": [
    {"name": "sda", "size": "465.8G", "type": "disk"},
    {"name": "nvme0n1", "size": "476.9G", "type": "disk"}
  ],
  "manufacture": "HP",
  "product_name": "HP Elite Slice G2 MS SRS Audio Ready"
}
```

### Automated Data Collection
For automated server inventory updates, schedule the agent with cron:

```bash
# Run agent every hour
0 * * * * /usr/bin/python3 /path/to/agent_linux.py --url http://nexhub.example.com --token YOUR_TOKEN
```

## UI/UX Design Patterns

NexHub follows consistent design patterns documented in [`DESIGN_CONFIG.md`](overwatch/templates/overwatch/DESIGN_CONFIG.md):

- **List Pages**: Searchable, filterable tables with pagination
- **Modals**: HTMX-powered for create/edit operations
- **Forms**: Clean, validated input with inline error messages
- **Detail Views**: Comprehensive information display with visual indicators
- **Color Coding**: Consistent semantic colors across the application

### Key Features
- **Real-time Search**: 250ms debounced search with HTMX
- **Responsive Design**: Mobile-first approach with Tailwind CSS
- **Accessibility**: ARIA labels, keyboard navigation support
- **Visual Feedback**: Loading states, success/error messages

## Version History

### v0.0.3 (Current)
- REST API with Django REST Framework
- Token-based authentication
- API endpoints for Server, Category, Tag, Subnet
- Agent script for automated data collection
- Bulk operations support

### v0.0.2
- Subnet CRUD with IP Pool management
- Dynamic From/To input fields for Static IP Pools
- Auto-calculated DHCP pools
- Detail modal with tag-style IP block display
- Updated DESIGN_CONFIG.md with new patterns

### v0.0.1
- Initial release
- Server management with full CRUD
- Notes system for servers
- Data Dictionary, Tags, Categories
- Professional UI with Tailwind + Flowbite

## Development

### Project Structure
```
nexhub/
├── nexhub/              # Project settings
│   ├── settings.py
│   ├── urls.py
│   └── wsgi.py
├── overwatch/           # Main application
│   ├── models.py        # Database models
│   ├── views.py         # View functions
│   ├── urls.py          # URL routing
│   ├── admin.py         # Admin configuration
│   ├── templates/       # HTML templates
│   └── migrations/      # Database migrations
├── static/              # Static files (CSS, JS)
├── templates/           # Base templates
│   └── base.html
├── manage.py
└── requirements.txt
```

### Contributing
1. Follow the established design patterns in DESIGN_CONFIG.md
2. Use consistent naming conventions (`{prefix}-` pattern for IDs)
3. Maintain HTMX patterns for dynamic interactions
4. Write migrations for all model changes
5. Update documentation for new features

## License

[Specify your license here]

## Contact

[Your contact information]

---

**Built with Django 6.0 | Styled with Tailwind CSS | Powered by HTMX**
