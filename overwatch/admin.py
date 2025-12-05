from django.contrib import admin

from .models import DataDictionary, IPAM, Note, Server, Subnet


@admin.register(Server)
class ServerAdmin(admin.ModelAdmin):
    list_display = ("hostname", "ip_address", "status", "os", "updated_at")
    search_fields = ("hostname", "ip_address", "uuid", "os", "status")
    list_filter = ("status", "os")


@admin.register(Subnet)
class SubnetAdmin(admin.ModelAdmin):
    list_display = ("name", "network", "vlan_id", "gateway")
    search_fields = ("name", "network")


@admin.register(IPAM)
class IPAMAdmin(admin.ModelAdmin):
    list_display = ("ip_address", "subnet", "status", "active", "server")
    search_fields = ("ip_address", "mac_address")
    list_filter = ("status", "active", "subnet")


@admin.register(DataDictionary)
class DataDictionaryAdmin(admin.ModelAdmin):
    list_display = ("original_keyword", "category", "standardized_value", "is_active")
    list_filter = ("category", "is_active")
    search_fields = ("original_keyword", "standardized_value")


@admin.register(Note)
class NoteAdmin(admin.ModelAdmin):
    list_display = ("server", "priority", "is_public", "updated_at")
    list_filter = ("priority", "is_public")
    search_fields = ("server__hostname", "content")
