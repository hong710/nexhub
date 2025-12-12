"""
Django signals for IPAM synchronization with Server table.
Automatically manages IPAM records when Servers or Subnets change.

Key Logic:
1. Subnet creation: Auto-populate static IP ranges in IPAM
2. Server save: Link both main IP and BMC IP to IPAM records
3. DHCP IPs: Create IPAM record on-demand if IP is in DHCP range
4. Missing subnet: Mark as "subnet_not_exist"
5. Hostname/MAC: Link nic_mac to main IP, bmc_mac to BMC IP
"""
from django.db.models.signals import post_save, post_delete, pre_delete
from django.dispatch import receiver
import ipaddress as ip_lib
from .models import Server, Subnet, IPAM


def find_subnet_for_ip(ip_str):
    """Find the subnet that contains this IP address."""
    try:
        ip_addr = ip_lib.ip_address(ip_str)
        for subnet in Subnet.objects.all():
            try:
                net = ip_lib.ip_network(subnet.network, strict=False)
                if ip_addr in net:
                    return subnet
            except (ValueError, AttributeError):
                pass
    except (ValueError, AttributeError):
        pass
    return None


def parse_ip_range(range_str):
    """Parse IP range string (e.g., '192.168.1.1-192.168.1.50') to list of IPs."""
    ips = []
    if '-' in range_str:
        start_ip, end_ip = range_str.split('-')
        start = ip_lib.ip_address(start_ip.strip())
        end = ip_lib.ip_address(end_ip.strip())
        
        current = start
        while current <= end:
            ips.append(str(current))
            current += 1
    else:
        ips.append(range_str.strip())
    
    return ips


def sync_ip_to_ipam(server, ip_address, is_bmc=False):
    """
    Sync a server IP (main or BMC) to IPAM table.
    
    Args:
        server: Server instance
        ip_address: IP to sync (main or BMC)
        is_bmc: True if this is BMC IP, False if main IP
    """
    if not ip_address:
        return
    
    try:
        # Find subnet for this IP
        subnet = find_subnet_for_ip(ip_address)
        
        if not subnet:
            # IP not in any subnet - create record with no subnet
            ipam_record, _ = IPAM.objects.get_or_create(
                ip_address=ip_address,
                defaults={
                    "status": "assigned",
                    "ip_type": "subnet_not_exist",
                    "server": server,
                    "is_bmc": is_bmc,
                    "hostname": server.hostname,
                    "mac_address": server.bmc_mac if is_bmc else server.nic_mac,
                }
            )
            
            # Always update to ensure latest server/mac/hostname
            ipam_record.server = server
            ipam_record.is_bmc = is_bmc
            ipam_record.hostname = server.hostname
            ipam_record.mac_address = server.bmc_mac if is_bmc else server.nic_mac
            ipam_record.status = "assigned"
            ipam_record.ip_type = "subnet_not_exist"
            ipam_record.save()
        else:
            # IP belongs to a subnet
            # Determine if it's in static or DHCP pool
            ip_type = "dhcp"
            
            # Check static pools
            if subnet.static_ip_pools:
                for pool_range in subnet.static_ip_pools:
                    if ip_address in parse_ip_range(pool_range):
                        ip_type = "static"
                        break
            
            # Get or create IPAM record
            ipam_record, _ = IPAM.objects.get_or_create(
                ip_address=ip_address,
                subnet=subnet,
                defaults={
                    "status": "assigned",
                    "ip_type": ip_type,
                    "server": server,
                    "is_bmc": is_bmc,
                    "hostname": server.hostname,
                    "mac_address": server.bmc_mac if is_bmc else server.nic_mac,
                }
            )
            
            # Always update to ensure latest server/mac/hostname
            ipam_record.server = server
            ipam_record.is_bmc = is_bmc
            ipam_record.hostname = server.hostname
            ipam_record.mac_address = server.bmc_mac if is_bmc else server.nic_mac
            ipam_record.status = "assigned"
            ipam_record.save()
            
    except Exception as e:
        print(f"Error syncing IP {ip_address} for server {server.hostname}: {e}")


@receiver(post_save, sender=Server)
def sync_server_to_ipam(sender, instance, created, update_fields, **kwargs):
    """
    When a Server is saved, sync both main IP and BMC IP to IPAM.
    """
    # Sync main IP
    if instance.ip_address:
        sync_ip_to_ipam(instance, instance.ip_address, is_bmc=False)
    
    # Sync BMC IP
    if instance.bmc_ip:
        sync_ip_to_ipam(instance, instance.bmc_ip, is_bmc=True)


@receiver(post_delete, sender=Server)
def cleanup_server_ipam(sender, instance, **kwargs):
    """
    When a Server is deleted, remove server reference from IPAM but keep records.
    """
    try:
        # For main IP - remove server reference if in static pool, delete if DHCP/orphan
        if instance.ip_address:
            ipam = IPAM.objects.filter(ip_address=instance.ip_address).first()
            if ipam:
                if ipam.ip_type == "static":
                    ipam.server = None
                    ipam.hostname = None
                    ipam.mac_address = None
                    ipam.status = "available"
                    ipam.save()
                else:
                    ipam.delete()
        
        # For BMC IP - remove server reference if in static pool, delete if DHCP/orphan
        if instance.bmc_ip:
            ipam = IPAM.objects.filter(ip_address=instance.bmc_ip).first()
            if ipam:
                if ipam.ip_type == "static":
                    ipam.server = None
                    ipam.hostname = None
                    ipam.mac_address = None
                    ipam.status = "available"
                    ipam.is_bmc = False
                    ipam.save()
                else:
                    ipam.delete()
    except Exception as e:
        print(f"Error cleaning up IPAM for deleted server {instance.hostname}: {e}")


@receiver(post_save, sender=Subnet)
def populate_static_ipam(sender, instance, created, **kwargs):
    """
    When a Subnet is created or static_ip_pools is updated,
    create IPAM records for all static IPs.
    """
    if created or 'static_ip_pools' in (kwargs.get('update_fields') or set()):
        try:
            # Clear existing static IPAM records for this subnet (that don't have servers)
            IPAM.objects.filter(subnet=instance, ip_type="static", server__isnull=True).delete()
            
            # Create new records for each static IP
            if instance.static_ip_pools:
                for pool_range in instance.static_ip_pools:
                    ips = parse_ip_range(pool_range)
                    
                    for ip in ips:
                        IPAM.objects.get_or_create(
                            ip_address=ip,
                            subnet=instance,
                            defaults={
                                "ip_type": "static",
                                "status": "available",
                            }
                        )
        except Exception as e:
            print(f"Error populating static IPAM for subnet {instance.name}: {e}")


@receiver(pre_delete, sender=Subnet)
def cleanup_subnet_ipam(sender, instance, **kwargs):
    """
    When a Subnet is deleted, delete all associated IPAM records.
    """
    try:
        IPAM.objects.filter(subnet=instance).delete()
    except Exception as e:
        print(f"Error cleaning up IPAM for deleted subnet {instance.name}: {e}")
