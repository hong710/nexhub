from django.contrib import admin

from .models import DataDictionary, IPAM, Note, Server, Subnet, Category, Tag


@admin.register(Server)
class ServerAdmin(admin.ModelAdmin):
    list_display = ("hostname", "ip_address", "device_type", "status", "os", "updated_at")
    search_fields = ("hostname", "ip_address", "uuid", "os", "status", "device_type")
    list_filter = ("status", "os", "device_type", "category")
    readonly_fields = ("uuid", "created_at", "updated_at")
    fieldsets = (
        ("Basic Information", {
            "fields": ("hostname", "uuid", "ip_address", "os", "status")
        }),
        ("Hardware Details", {
            "fields": ("manufacture", "product_name", "cpu", "total_mem", "mem_details", "device_type")
        }),
        ("Network & Storage", {
            "fields": ("nic_mac", "bmc_ip", "bmc_mac", "disk_count", "disk_details")
        }),
        ("Management", {
            "fields": ("category", "accelerator", "bios_version", "bios_release_date")
        }),
        ("Location", {
            "fields": ("building", "room", "rack", "location"),
            "classes": ("collapse",)
        }),
        ("Timestamps", {
            "fields": ("created_at", "updated_at"),
            "classes": ("collapse",)
        }),
    )


@admin.register(Category)
class CategoryAdmin(admin.ModelAdmin):
    list_display = ("device_type", "updated_at")
    search_fields = ("device_type",)
    readonly_fields = ("created_at", "updated_at")


@admin.register(Tag)
class TagAdmin(admin.ModelAdmin):
    list_display = ("name", "updated_by", "updated_at")
    search_fields = ("name",)
    readonly_fields = ("created_at", "updated_at")



@admin.register(Subnet)
class SubnetAdmin(admin.ModelAdmin):
    list_display = ("name", "network", "vlan_id", "gateway")
    search_fields = ("name", "network")
    readonly_fields = ("created_at", "updated_at")


@admin.register(IPAM)
class IPAMAdmin(admin.ModelAdmin):
    list_display = ("ip_address", "subnet", "hostname", "status", "active", "ip_type")
    search_fields = ("ip_address", "mac_address", "hostname")
    list_filter = ("status", "active", "subnet", "ip_type")
    readonly_fields = ("created_at", "updated_at", "ip_type")
    
    fieldsets = (
        ("IP Address Information", {
            "fields": ("ip_address", "subnet", "ip_type", "active")
        }),
        ("Allocation", {
            "fields": ("status", "server", "hostname", "mac_address")
        }),
        ("Device Details (Read-only)", {
            "fields": ("platform", "manufacturer"),
            "classes": ("collapse",)
        }),
        ("Reserved IP Details", {
            "fields": ("description",),
            "description": "Only editable when status is 'reserved'",
            "classes": ("collapse",)
        }),
        ("Timestamps", {
            "fields": ("created_at", "updated_at"),
            "classes": ("collapse",)
        }),
    )
    
    def get_readonly_fields(self, request, obj=None):
        """Make description field read-only unless status is 'reserved'."""
        readonly = list(self.readonly_fields)
        if obj and obj.status != "reserved":
            readonly.append("description")
        return readonly


@admin.register(DataDictionary)
class DataDictionaryAdmin(admin.ModelAdmin):
    list_display = ("original_keyword", "translate_from", "category", "standardized_value", "is_active")
    list_filter = ("category", "is_active", "translate_from")
    search_fields = ("original_keyword", "standardized_value")
    readonly_fields = ("created_at", "updated_at")
    fieldsets = (
        ("Translation Rule", {
            "fields": ("translate_from", "original_keyword", "standardized_value")
        }),
        ("Classification", {
            "fields": ("category", "is_active")
        }),
        ("Timestamps", {
            "fields": ("created_at", "updated_at"),
            "classes": ("collapse",)
        }),
    )


@admin.register(Note)
class NoteAdmin(admin.ModelAdmin):
    list_display = ("server", "priority", "is_public", "updated_at")
    list_filter = ("priority", "is_public")
    search_fields = ("server__hostname", "content")
    readonly_fields = ("created_at", "updated_at")

