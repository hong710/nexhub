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
    ("allocated", "Allocated"),
    ("reserved", "Reserved"),
    ("quarantine", "Quarantine"),
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

    device_type = models.CharField(max_length=100, unique=True)

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

    def __str__(self) -> str:
        return self.hostname


class Subnet(BaseModel):
    name = models.CharField(max_length=100, unique=True)
    network = models.CharField(max_length=18)
    vlan_id = models.PositiveIntegerField(blank=True, null=True)
    gateway = models.GenericIPAddressField(blank=True, null=True)
    description = models.TextField(blank=True, null=True)

    def __str__(self) -> str:
        return f"{self.name} ({self.network})"


class IPAM(BaseModel):
    ip_address = models.GenericIPAddressField(unique=True)
    subnet = models.ForeignKey(Subnet, on_delete=models.CASCADE, related_name="ip_addresses")
    active = models.BooleanField(default=True)
    server = models.ForeignKey(Server, on_delete=models.SET_NULL, related_name="ip_assignments", blank=True, null=True)
    status = models.CharField(max_length=20, choices=IPAM_STATUS_CHOICES, default="available")
    mac_address = models.CharField(max_length=17, blank=True, null=True)
    description = models.TextField(blank=True, null=True)

    def __str__(self) -> str:
        return f"{self.ip_address} ({self.status})"


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
