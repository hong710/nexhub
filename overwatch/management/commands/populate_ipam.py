"""
Management command to populate IPAM table from subnets and servers.
This should be run after adding the new IPAM model to the database.
"""
from django.core.management.base import BaseCommand
from django.db import transaction
import ipaddress as ip_lib
from overwatch.models import Subnet, Server, IPAM


class Command(BaseCommand):
    help = 'Populate IPAM table from subnet static pools and sync with existing servers'
    
    def add_arguments(self, parser):
        parser.add_argument(
            '--clear',
            action='store_true',
            help='Clear all IPAM records before repopulating'
        )
    
    def handle(self, *args, **options):
        if options['clear']:
            count, _ = IPAM.objects.all().delete()
            self.stdout.write(self.style.SUCCESS(f'✓ Cleared {count} IPAM records'))
        
        with transaction.atomic():
            # Step 1: Populate static IPs from subnets
            static_count = self._populate_static_ips()
            self.stdout.write(self.style.SUCCESS(f'✓ Created {static_count} static IPAM records'))
            
            # Step 2: Sync existing servers
            allocated_count = self._sync_servers()
            self.stdout.write(self.style.SUCCESS(f'✓ Updated {allocated_count} IPAM records from servers'))
            
            # Step 3: Summary
            total_records = IPAM.objects.count()
            available = IPAM.objects.filter(status='available').count()
            allocated = IPAM.objects.filter(status='allocated').count()
            reserved = IPAM.objects.filter(status='reserved').count()
            
            self.stdout.write(self.style.SUCCESS(f'\n📊 IPAM Summary:'))
            self.stdout.write(f'   Total Records: {total_records}')
            self.stdout.write(f'   Available: {available}')
            self.stdout.write(f'   Allocated: {allocated}')
            self.stdout.write(f'   Reserved: {reserved}')
    
    def _populate_static_ips(self):
        """Create IPAM records for all static IP pools."""
        created_count = 0
        
        for subnet in Subnet.objects.filter(static_ip_pools__isnull=False):
            if not subnet.static_ip_pools:
                continue
            
            for pool_range in subnet.static_ip_pools:
                ips = self._parse_ip_range(pool_range)
                
                for ip in ips:
                    _, created = IPAM.objects.get_or_create(
                        ip_address=ip,
                        subnet=subnet,
                        defaults={
                            'ip_type': 'static',
                            'status': 'available',
                            'active': True,
                        }
                    )
                    if created:
                        created_count += 1
        
        return created_count
    
    def _sync_servers(self):
        """Sync existing servers with IPAM."""
        updated_count = 0
        
        for server in Server.objects.filter(ip_address__isnull=False):
            try:
                # Find subnet for this IP
                subnet = self._find_subnet_for_ip(server.ip_address)
                if not subnet:
                    continue
                
                # Create or update IPAM record
                ipam, created = IPAM.objects.get_or_create(
                    ip_address=server.ip_address,
                    subnet=subnet,
                    defaults={
                        'ip_type': 'dhcp',
                        'server': server,
                        'status': 'allocated',
                        'active': True,
                    }
                )
                
                if not created:
                    # Update existing record
                    ipam.server = server
                    ipam.ip_type = 'dhcp'
                    ipam.sync_from_server()
                    ipam.save()
                    updated_count += 1
            except Exception as e:
                self.stdout.write(
                    self.style.ERROR(f'Error syncing server {server.hostname}: {e}')
                )
        
        return updated_count
    
    def _parse_ip_range(self, range_str):
        """Parse IP range string to list of IPs."""
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
    
    def _find_subnet_for_ip(self, ip_address):
        """Find which subnet contains this IP."""
        try:
            ip = ip_lib.ip_address(ip_address)
            for subnet in Subnet.objects.all():
                try:
                    net = ip_lib.ip_network(subnet.network, strict=False)
                    if ip in net:
                        return subnet
                except (ValueError, AttributeError):
                    pass
        except (ValueError, AttributeError):
            pass
        
        return None
