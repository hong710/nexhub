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

### v0.0.2 (Current)
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
