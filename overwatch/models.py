from django.contrib.auth import get_user_model
from django.db import models


User = get_user_model()


class BaseModel(models.Model):
    """Shared audit fields."""

    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)
    updated_by = models.ForeignKey(
        User, null=True, blank=True, on_delete=models.SET_NULL, related_name="%(class)s_updated"
    )

    class Meta:
        abstract = True


SERVER_STATUS_CHOICES = [
    ("active", "Active"),
    ("inactive", "Inactive"),
    ("maintenance", "Maintenance"),
    ("decommissioned", "Decommissioned"),
]

DATA_SOURCE_CHOICES = [
    ("manual", "Manual"),
    ("discovery", "Discovery"),
    ("import", "Import"),
    ("api", "API"),
    ("pull request", "Pull Request"),
]

IPAM_STATUS_CHOICES = [
    ("available", "Available"),
    ("assigned", "Assigned"),
    ("reserved", "Reserved"),
    ("conflict", "Conflict"),
]

DICTIONARY_CATEGORY_CHOICES = [
    ("vendor", "Vendor"),
    ("os", "Operating System"),
    ("cpu", "CPU"),
    ("platform", "Platform"),
    ("environment", "Environment"),
    ("accelerator", "Accelerator"),
    ("NIC", "NIC"),
    ("other", "Other"),
]

NOTE_PRIORITY_CHOICES = [
    ("info", "Info"),
    ("low", "Low"),
    ("medium", "Medium"),
    ("high", "High"),
]


class Category(BaseModel):
    """Device category for servers."""

    ADDED_BY_CHOICES = [
        ("agent", "Agent"),
        ("manual", "Manual"),
    ]

    device_type = models.CharField(max_length=100, unique=True)
    added_by = models.CharField(max_length=10, choices=ADDED_BY_CHOICES, default="manual")

    def __str__(self) -> str:
        return self.device_type


class Tag(BaseModel):
    """Reusable tag for servers."""

    name = models.CharField(max_length=100, unique=True)
    description = models.TextField(blank=True, null=True)

    def __str__(self) -> str:
        return self.name


class Server(BaseModel):
    # Basic Information
    uuid = models.CharField(max_length=36, unique=True, blank=True, null=True)
    hostname = models.CharField(max_length=255)

    # Network Information
    ip_address = models.GenericIPAddressField(blank=True, null=True)
    nic_mac = models.CharField(max_length=17, blank=True, null=True)
    bmc_ip = models.GenericIPAddressField(blank=True, null=True)
    bmc_mac = models.CharField(max_length=17, blank=True, null=True)

    # Hardware Information
    manufacture = models.CharField(max_length=100, blank=True, null=True)
    product_name = models.CharField(max_length=100, blank=True, null=True)
    device_type = models.CharField(max_length=50, blank=True, null=True, help_text="Device type: server, desktop, laptop, embedded, other")

    # CPU Information
    cpu = models.CharField(max_length=255, blank=True, null=True)
    core_count = models.PositiveIntegerField(blank=True, null=True)
    sockets = models.PositiveIntegerField(blank=True, null=True)

    # Memory Information
    total_mem = models.PositiveIntegerField(blank=True, null=True, help_text="Total memory in GB")
    mem_details = models.JSONField(blank=True, null=True)

    # Storage Information
    disk_count = models.PositiveIntegerField(blank=True, null=True)
    disk_details = models.JSONField(blank=True, null=True)

    # BIOS Information
    bios_version = models.CharField(max_length=100, blank=True, null=True)
    bios_release_date = models.DateField(blank=True, null=True)

    # Software Information
    os = models.CharField(max_length=100, blank=True, null=True)
    os_version = models.CharField(max_length=100, blank=True, null=True)
    kernel = models.CharField(max_length=100, blank=True, null=True)

    # Location Information
    building = models.CharField(max_length=100, blank=True, null=True)
    room = models.CharField(max_length=100, blank=True, null=True)
    rack = models.CharField(max_length=50, blank=True, null=True)
    location = models.CharField(max_length=10, blank=True, null=True)

    # Management Information
    status = models.CharField(max_length=20, choices=SERVER_STATUS_CHOICES, default="active")
    assign_to = models.CharField(max_length=100, blank=True, null=True)
    last_login = models.CharField(max_length=100, blank=True, null=True)
    user_folders = models.JSONField(blank=True, null=True)

    # Additional Hardware
    accelerator = models.JSONField(blank=True, null=True)
    network_interfaces = models.JSONField(blank=True, null=True)
    expansion_slots = models.JSONField(blank=True, null=True)

    # Monitoring & Management Flags
    pdu_connection = models.BooleanField(default=False)
    tags = models.ManyToManyField(Tag, related_name="servers", blank=True)
    pdu_ip = models.GenericIPAddressField(blank=True, null=True)
    pdu_port_number = models.CharField(max_length=20, blank=True, null=True)

    # Category
    category = models.ForeignKey(Category, on_delete=models.SET_NULL, related_name="servers", blank=True, null=True)

    # Data Source & Quality
    data_source = models.CharField(max_length=20, choices=DATA_SOURCE_CHOICES, blank=True, null=True)

    # Miscellaneous
    misc = models.JSONField(blank=True, null=True)

    def _translate_field(self, field_name: str, value: str) -> str:
        """Translate a field value using DataDictionary if available."""
        if not value:
            return value
        
        # Try to find a translation
        try:
            translation = DataDictionary.objects.filter(
                translate_from=field_name,
                original_keyword__iexact=value,
                is_active=True
            ).first()
            if translation:
                return translation.standardized_value
        except Exception:
            pass
        
        return value
    
    def save(self, *args, **kwargs):
        """Override save to apply DataDictionary translations."""
        # Apply translations for specific fields
        if self.product_name:
            self.product_name = self._translate_field("product_name", self.product_name)
        
        if self.manufacture:
            self.manufacture = self._translate_field("manufacture", self.manufacture)
        
        if self.cpu:
            self.cpu = self._translate_field("cpu", self.cpu)
        
        if self.os:
            self.os = self._translate_field("os", self.os)
        
        super().save(*args, **kwargs)

    def __str__(self) -> str:
        return self.hostname


class Subnet(BaseModel):
    name = models.CharField(max_length=100, unique=True)
    network = models.CharField(max_length=18)
    vlan_id = models.PositiveIntegerField(blank=True, null=True)
    gateway = models.GenericIPAddressField(blank=True, null=True)
    description = models.TextField(blank=True, null=True)
    static_ip_pools = models.JSONField(blank=True, null=True, help_text="List of static IP ranges, e.g. ['10.0.1.1-10.0.1.50']")
    dhcp_pools = models.JSONField(blank=True, null=True, help_text="List of DHCP IP ranges (auto-calculated)")

    def __str__(self) -> str:
        return f"{self.name} ({self.network})"

    def get_usable_ips(self) -> int:
        """Calculate total usable IPs in the subnet."""
        try:
            import ipaddress as ip_lib
            net = ip_lib.ip_network(self.network, strict=False)
            # Usable IPs = total IPs - network address - broadcast address
            return net.num_addresses - 2 if net.num_addresses > 2 else 0
        except (ValueError, AttributeError):
            return 0

    def get_available_ips(self) -> int:
        """Calculate available static IPs (not allocated in IPAM) - only counts static pool IPs."""
        try:
            import ipaddress as ip_lib
            
            if not self.static_ip_pools:
                return 0
            
            # Get all IPs in static pools
            static_pool_ips = set()
            for pool_range in self.static_ip_pools:
                if '-' in pool_range:
                    start_ip, end_ip = pool_range.split('-')
                    start = ip_lib.ip_address(start_ip.strip())
                    end = ip_lib.ip_address(end_ip.strip())
                    current = start
                    while current <= end:
                        static_pool_ips.add(str(current))
                        current += 1
            
            # Get allocated IPs from IPAM that are in static pool
            # Status 'available' means not allocated, so we count non-available static IPs
            allocated_static_ips = set(
                self.ip_addresses.filter(
                    ip_type='static'
                ).exclude(
                    status='available'
                ).values_list('ip_address', flat=True)
            )
            
            # Available static = static pool total - allocated static
            return len(static_pool_ips - allocated_static_ips)
        except (ValueError, AttributeError):
            return 0

    def get_allocation_percentage(self) -> float:
        """Calculate the percentage of static IPs allocated."""
        if not self.static_ip_pools:
            return 0.0
        
        # Get total static IPs
        total_static = 0
        try:
            import ipaddress as ip_lib
            for pool_range in self.static_ip_pools:
                if '-' in pool_range:
                    start_ip, end_ip = pool_range.split('-')
                    start = ip_lib.ip_address(start_ip.strip())
                    end = ip_lib.ip_address(end_ip.strip())
                    total_static += int(end) - int(start) + 1
        except (ValueError, AttributeError):
            return 0.0
        
        if total_static == 0:
            return 0.0
        
        available = self.get_available_ips()
        allocated = total_static - available
        return (allocated / total_static) * 100

    def calculate_dhcp_pools(self) -> list[str]:
        """Calculate DHCP pools based on static IP pools and network range."""
        try:
            import ipaddress as ip_lib
            net = ip_lib.ip_network(self.network, strict=False)
            all_ips = set(net.hosts())
            
            # Parse static IP pools and collect all static IPs
            static_ips = set()
            if self.static_ip_pools:
                for pool_range in self.static_ip_pools:
                    if '-' in pool_range:
                        start_ip, end_ip = pool_range.split('-')
                        start_ip = ip_lib.ip_address(start_ip.strip())
                        end_ip = ip_lib.ip_address(end_ip.strip())
                        # Add all IPs in the range
                        current = start_ip
                        while current <= end_ip:
                            static_ips.add(current)
                            current += 1
            
            # DHCP pool = all usable IPs - static IPs - gateway
            dhcp_ips = all_ips - static_ips
            if self.gateway:
                try:
                    dhcp_ips.discard(ip_lib.ip_address(self.gateway))
                except ValueError:
                    pass
            
            # Convert to sorted list and create ranges
            if not dhcp_ips:
                return []
            
            sorted_ips = sorted(list(dhcp_ips))
            ranges = []
            start = sorted_ips[0]
            prev = sorted_ips[0]
            
            for ip in sorted_ips[1:]:
                if int(ip) - int(prev) > 1:
                    # Gap found, close current range
                    if start == prev:
                        ranges.append(str(start))
                    else:
                        ranges.append(f"{start}-{prev}")
                    start = ip
                prev = ip
            
            # Close last range
            if start == prev:
                ranges.append(str(start))
            else:
                ranges.append(f"{start}-{prev}")
            
            return ranges
        except (ValueError, AttributeError, TypeError):
            return []

    def get_static_ip_count(self) -> int:
        """Count total IPs in static pools."""
        if not self.static_ip_pools:
            return 0
        try:
            import ipaddress as ip_lib
            count = 0
            for pool_range in self.static_ip_pools:
                if '-' in pool_range:
                    start_ip, end_ip = pool_range.split('-')
                    start = ip_lib.ip_address(start_ip.strip())
                    end = ip_lib.ip_address(end_ip.strip())
                    count += int(end) - int(start) + 1
            return count
        except (ValueError, AttributeError, TypeError):
            return 0

    def get_dhcp_ip_count(self) -> int:
        """Count total IPs in DHCP pools."""
        if not self.dhcp_pools:
            return 0
        try:
            import ipaddress as ip_lib
            count = 0
            for pool_range in self.dhcp_pools:
                if '-' in pool_range:
                    start_ip, end_ip = pool_range.split('-')
                    start = ip_lib.ip_address(start_ip.strip())
                    end = ip_lib.ip_address(end_ip.strip())
                    count += int(end) - int(start) + 1
                else:
                    count += 1
            return count
        except (ValueError, AttributeError, TypeError):
            return 0


class IPAM(BaseModel):
    """IP Address Management tracking - synced with Server table."""
    
    ip_address = models.GenericIPAddressField()
    subnet = models.ForeignKey(Subnet, on_delete=models.CASCADE, related_name="ip_addresses", blank=True, null=True)
    active = models.BooleanField(default=True, help_text="Ping check - IP is responding")
    server = models.ForeignKey(Server, on_delete=models.SET_NULL, related_name="ip_assignments", blank=True, null=True)
    is_bmc = models.BooleanField(default=False, help_text="Is this a BMC (Baseboard Management Controller) IP?")
    
    # Status tracking
    status = models.CharField(max_length=20, choices=IPAM_STATUS_CHOICES, default="available")
    ip_type = models.CharField(max_length=30, choices=[
        ("static", "Static"),
        ("dhcp", "DHCP"),
        ("subnet_not_exist", "Subnet Not Exist")
    ], default="static")
    
    # Device information (synced from Server)
    hostname = models.CharField(max_length=255, blank=True, null=True)
    mac_address = models.CharField(max_length=17, blank=True, null=True)
    platform = models.CharField(max_length=100, blank=True, null=True)
    manufacturer = models.CharField(max_length=100, blank=True, null=True)
    
    # Additional tracking
    description = models.TextField(blank=True, null=True, help_text="Only editable when status is 'reserved'")
    
    class Meta:
        unique_together = [["ip_address", "subnet"]]
        indexes = [
            models.Index(fields=["subnet", "status"]),
            models.Index(fields=["ip_address"]),
        ]

    def __str__(self) -> str:
        return f"{self.ip_address} ({self.status})"
    
    def sync_from_server(self):
        """Sync IPAM record with Server data."""
        if self.server:
            self.hostname = self.server.hostname
            self.mac_address = self.server.nic_mac
            self.platform = self.server.device_type
            self.manufacturer = self.server.manufacture
            self.status = "assigned"
            # Check if this is a BMC IP
            self.is_bmc = (self.ip_address == self.server.bmc_ip)
        else:
            self.status = "available"
            self.hostname = None
            self.mac_address = None
            self.is_bmc = False


class DataDictionary(BaseModel):
    translate_from = models.CharField(max_length=200, blank=True, null=True)
    original_keyword = models.CharField(max_length=255)
    category = models.CharField(max_length=50, choices=DICTIONARY_CATEGORY_CHOICES)
    standardized_value = models.CharField(max_length=255)
    description = models.TextField(blank=True, null=True)
    is_active = models.BooleanField(default=True)

    class Meta:
        unique_together = [["original_keyword", "category"]]
        verbose_name_plural = "Data Dictionaries"

    def __str__(self) -> str:
        return f"{self.original_keyword} -> {self.standardized_value}"


class Note(BaseModel):
    server = models.ForeignKey(Server, on_delete=models.CASCADE, related_name="notes")
    content = models.TextField()
    priority = models.CharField(max_length=10, choices=NOTE_PRIORITY_CHOICES, default="info")
    is_public = models.BooleanField(default=True)

    def __str__(self) -> str:
        return f"Note for {self.server.hostname} ({self.priority})"


class AuditEvent(models.Model):
    """User activity log for app events (kept for 90 days)."""

    ACTION_CHOICES = [
        ("create", "Create"),
        ("update", "Update"),
        ("delete", "Delete"),
        ("note", "Note"),
        ("ipam", "IPAM"),
        ("other", "Other"),
    ]

    user = models.ForeignKey(User, on_delete=models.SET_NULL, null=True, blank=True)
    action = models.CharField(max_length=20, choices=ACTION_CHOICES)
    entity_type = models.CharField(max_length=100)
    entity_id = models.PositiveIntegerField(null=True, blank=True)
    entity_repr = models.CharField(max_length=255, blank=True, null=True)
    message = models.TextField(blank=True, null=True)
    created_at = models.DateTimeField(auto_now_add=True, db_index=True)

    class Meta:
        indexes = [
            models.Index(fields=["created_at", "entity_type", "action"]),
        ]
        ordering = ["-created_at"]

    def __str__(self) -> str:
        user = self.user.username if self.user else "system"
        return f"[{self.created_at:%Y-%m-%d %H:%M}] {user} {self.action} {self.entity_type} {self.entity_repr}"
