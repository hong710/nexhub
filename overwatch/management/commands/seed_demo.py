import uuid
from datetime import date
from itertools import cycle

from django.core.management.base import BaseCommand

from overwatch.models import IPAM, Note, Server, Subnet


def mac_from_index(idx: int) -> str:
    """Generate a deterministic MAC-like address from an index."""
    return ":".join(
        [
            "02",
            "00",
            f"{idx:02x}",
            f"{(idx * 2) % 256:02x}",
            f"{(idx * 3) % 256:02x}",
            f"{(idx * 4) % 256:02x}",
        ]
    )


class Command(BaseCommand):
    help = "Seed demo data: 3 subnets, 30 servers, IPAM entries, and notes."

    def handle(self, *args, **options):
        # Create a few subnets
        subnet_specs = [
            ("Compute A", "10.0.1.0/24", 101, "10.0.1.1"),
            ("Compute B", "10.0.2.0/24", 102, "10.0.2.1"),
            ("Compute C", "10.0.3.0/24", 103, "10.0.3.1"),
        ]
        subnets = []
        for name, network, vlan, gw in subnet_specs:
            subnet, _ = Subnet.objects.get_or_create(
                name=name,
                defaults={"network": network, "vlan_id": vlan, "gateway": gw, "description": f"{name} VLAN {vlan}"},
            )
            subnets.append(subnet)

        statuses = ["active", "inactive", "maintenance", "decommissioned"]
        os_names = ["Ubuntu", "Debian", "CentOS", "Rocky", "Alma", "Windows"]
        cpu_models = ["6338", "6421N", "8460", "4314", "6112", "8352Y", "8380"]
        data_sources = ["manual", "discovery", "import", "api"]
        manufactures = ["Dell", "HPE", "Intel", "Quanta", "Microserver"]
        product_names = [
            "PowerEdge R740",
            "PowerEdge R750",
            "HPE Edgeline EL930t",
            "HPE Edgeline EL920",
            "HPE ProLiant DL380",
            "Quanta Cloud D52B",
            "Quanta Cloud D43K",
            "Intel Server D50TNP",
            "Intel Server R1304",
            "Microserver Edge 120",
            "Microserver Edge 220",
        ]

        status_cycle = cycle(statuses)
        os_cycle = cycle(os_names)
        cpu_cycle = cycle(cpu_models)
        source_cycle = cycle(data_sources)
        subnet_cycle = cycle(subnets)
        manu_cycle = cycle(manufactures)
        product_cycle = cycle(product_names)

        created_servers = 0
        created_ipams = 0
        created_notes = 0

        for i in range(1, 61):
            hostname = f"server-{i:03d}"
            subnet = next(subnet_cycle)
            octet = 10 + i  # start IPs at .10 to leave room for infra
            ip_addr = subnet.network.replace(".0/24", f".{octet}")
            bmc_ip = subnet.network.replace(".0/24", f".{200 + i}")

            server_defaults = {
                "uuid": str(uuid.uuid4()),
                "ip_address": ip_addr,
                "nic_mac": mac_from_index(i),
                "bmc_ip": bmc_ip,
                "bmc_mac": mac_from_index(200 + i),
                "manufacture": next(manu_cycle),
                "product_name": next(product_cycle),
                "cpu": next(cpu_cycle),
                "core_count": 20 + (i % 5) * 4,
                "sockets": 2,
                "total_mem": 128 + (i % 3) * 64,
                "mem_details": {"slots": 16, "dimms": "16x16GB DDR4"},
                "disk_count": 8,
                "disk_details": {"layout": "8x2TB SSD"},
                "bios_version": f"2.{i % 5}",
                "bios_release_date": date(2023, (i % 12) + 1, min(28, (i % 27) + 1)),
                "os": next(os_cycle),
                "os_version": "22.04",
                "kernel": "5.15.0",
                "building": "DC1",
                "room": "R1",
                "rack": f"A{i%10:02d}",
                "location": "HQ",
                "status": next(status_cycle),
                "assign_to": "ops-team",
                "last_login": "cron-user",
                "user_folders": {"home": f"/home/server-{i:03d}"},
                "accelerator": {"gpus": i % 4},
                "network_interfaces": {"bond0": ["eth0", "eth1"]},
                "expansion_slots": {"pcie": 3},
                "tags": "prod,db" if i % 5 == 0 else ("lab,dev" if i % 2 == 0 else "prod,app"),
                "pdu_connection": bool(i % 2),
                "data_source": next(source_cycle),
                "misc": {"note": "seeded record"},
            }

            server, created = Server.objects.update_or_create(hostname=hostname, defaults=server_defaults)
            created_servers += int(created)

            ipam_defaults = {
                "subnet": subnet,
                "active": True,
                "server": server,
                "status": "allocated",
                "mac_address": server.nic_mac,
                "description": f"Auto-assigned to {hostname}",
            }
            ipam, created_ip = IPAM.objects.update_or_create(ip_address=ip_addr, defaults=ipam_defaults)
            created_ipams += int(created_ip)

            note_defaults = {
                "priority": "medium",
                "is_public": True,
                "content": f"Initial note for {hostname}. Status: {server.status}.",
            }
            note, created_note = Note.objects.get_or_create(server=server, defaults=note_defaults)
            created_notes += int(created_note)

        self.stdout.write(self.style.SUCCESS(f"Subnets: {len(subnets)} (created or existing)"))
        self.stdout.write(self.style.SUCCESS(f"Servers created: {created_servers}/30 (others updated)"))
        self.stdout.write(self.style.SUCCESS(f"IPAM created: {created_ipams}/30 (others updated)"))
        self.stdout.write(self.style.SUCCESS(f"Notes created: {created_notes}/30 (others already existed)"))
