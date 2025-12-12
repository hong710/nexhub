from rest_framework import serializers

from overwatch.models import Category, Server, Subnet, Tag, IPAM


class CategorySerializer(serializers.ModelSerializer):
    class Meta:
        model = Category
        fields = ["id", "device_type", "created_at", "updated_at"]
        read_only_fields = ["id", "created_at", "updated_at"]


class TagSerializer(serializers.ModelSerializer):
    class Meta:
        model = Tag
        fields = ["id", "name", "description", "created_at", "updated_at"]
        read_only_fields = ["id", "created_at", "updated_at"]


class ServerSerializer(serializers.ModelSerializer):
    # Read nested objects
    tags_detail = TagSerializer(source="tags", many=True, read_only=True)
    category_detail = CategorySerializer(source="category", read_only=True)

    # Write by ID
    tags = serializers.PrimaryKeyRelatedField(many=True, queryset=Tag.objects.all(), required=False)
    category = serializers.PrimaryKeyRelatedField(queryset=Category.objects.all(), required=False, allow_null=True)

    class Meta:
        model = Server
        fields = [
            # IDs
            "id",
            "uuid",
            # Basic
            "hostname",
            # Network
            "ip_address",
            "nic_mac",
            "bmc_ip",
            "bmc_mac",
            # Hardware
            "manufacture",
            "product_name",
            "device_type",
            # CPU
            "cpu",
            "core_count",
            "sockets",
            # Memory
            "total_mem",
            "mem_details",
            # Storage
            "disk_count",
            "disk_details",
            # BIOS
            "bios_version",
            "bios_release_date",
            # Software
            "os",
            "os_version",
            "kernel",
            # Location
            "building",
            "room",
            "rack",
            "location",
            # Management
            "status",
            "assign_to",
            "last_login",
            "user_folders",
            # Additional Hardware
            "accelerator",
            "network_interfaces",
            "expansion_slots",
            # Monitoring
            "pdu_connection",
            "pdu_ip",
            "pdu_port_number",
            # Relations
            "tags",
            "tags_detail",
            "category",
            "category_detail",
            # Data Source
            "data_source",
            # Misc
            "misc",
            # Audit
            "created_at",
            "updated_at",
        ]
        read_only_fields = ["id", "created_at", "updated_at", "tags_detail", "category_detail"]


class SubnetSerializer(serializers.ModelSerializer):
    # Calculate fields
    usable_ips = serializers.IntegerField(read_only=True)
    available_ips = serializers.IntegerField(read_only=True)
    allocation_percentage = serializers.FloatField(read_only=True)

    class Meta:
        model = Subnet
        fields = [
            "id",
            "name",
            "network",
            "description",
            "vlan",
            "gateway",
            "dns_servers",
            "static_ip_pools",
            "dhcp_pools",
            "usable_ips",
            "available_ips",
            "allocation_percentage",
            "created_at",
            "updated_at",
        ]
        read_only_fields = ["id", "created_at", "updated_at", "usable_ips", "available_ips", "allocation_percentage"]

    def to_representation(self, instance):
        """Add calculated fields to response."""
        representation = super().to_representation(instance)
        representation["usable_ips"] = instance.get_usable_ips()
        representation["available_ips"] = instance.get_available_ips()
        representation["allocation_percentage"] = instance.get_allocation_percentage()
        return representation


class IPAMSerializer(serializers.ModelSerializer):
    """Serializer for IPAM IP address records."""
    subnet_name = serializers.CharField(source="subnet.name", read_only=True)
    server_hostname = serializers.CharField(source="server.hostname", read_only=True, allow_null=True)
    
    class Meta:
        model = IPAM
        fields = [
            "id",
            "ip_address",
            "subnet",
            "subnet_name",
            "status",
            "active",
            "ip_type",
            "server",
            "server_hostname",
            "hostname",
            "mac_address",
            "platform",
            "manufacturer",
            "description",
            "created_at",
            "updated_at",
        ]
        read_only_fields = ["id", "created_at", "updated_at", "subnet_name", "server_hostname"]
    
    def validate(self, data):
        """Validate that description is only editable when status is 'reserved'."""
        instance = self.instance
        if instance and instance.status != "reserved" and "description" in self.initial_data:
            if self.initial_data.get("description") != instance.description:
                raise serializers.ValidationError(
                    {"description": "Description can only be edited when status is 'reserved'"}
                )
        return data
