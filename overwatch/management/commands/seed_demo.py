import uuid
import random
from datetime import date
from itertools import cycle

from django.core.management.base import BaseCommand
from django.db import transaction

from overwatch.models import (
    IPAM,
    Note,
    Server,
    Subnet,
    Category,
    Tag,
)

# =========================
# Utility Helper Functions
# =========================

def mac_from_index(idx: int) -> str:
    """Deterministic MAC-like address generator."""
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


def rand_bios():
    """Generate realistic BIOS string."""
    prefix = random.choice(["SE5C7411.86B", "A32.0.18", "U40.3.9"])
    middle = f"{random.randint(1000,9999)}.{random.randint(1000,9999)}"
    datecode = f"{random.randint(230101, 251231)}"
    return f"{prefix}.{middle}.{datecode}"


def pick_weighted(weights: dict):
    """Pick random item based on weighted probability."""
    items = list(weights.keys())
    probs = list(weights.values())
    return random.choices(items, probs)[0]

# ==========================================
# Categories, Tags, OS/KERNEL Tables
# ==========================================

def seed_categories():
    categories = [
        "Server",
        "Switch",
        "PDU",
        "Debug Tool",
        "NUC Platform",
        "Windows PC",
    ]
    objs = {}
    for c in categories:
        obj, _ = Category.objects.get_or_create(device_type=c)
        objs[c] = obj
    return objs


def seed_tags():
    tag_list = ["MRC", "XRan_setup", "Demo", "CI/CD", "Production_App"]
    tags = []
    for t in tag_list:
        tag, _ = Tag.objects.get_or_create(name=t, defaults={"description": f"{t} tag"})
        tags.append(tag)
    return tags


# ================================
# OS + Kernel definitions
# ================================

UBUNTU_22_KERNELS = ["5.12.1009", "5.12.1032", "5.12.1052"]
UBUNTU_24_KERNELS = ["6.8.1002", "6.8.1003", "6.8.1022"]

RHEL_KERNEL = "6.12.0-55.9.1.el10_0"
CENTOS_KERNEL = "6.12.0-55.9.1.el10_0"

WRCP_24_KERNEL = "6.8.1"
WRCP_25_KERNELS = ["6.8.1", "5.12.1"]

TALOS_KERNEL = "6.6.0"


def pick_os_and_kernel(idx):
    """
    Rotates OS assignment across all required distributions.
    We use a stable pattern so Talos appears exactly 2 times.
    """

    order = [
        "Ubuntu-22",
        "Ubuntu-24",
        "RHEL10",
        "CentOS10",
        "WRCP24",
        "WRCP25",
        "Ubuntu-22",
        "Ubuntu-24",
        "WRCP24",
        "Ubuntu-22",
        "TALOS",        # Talos appears purposely in rotation
        "Ubuntu-24",
        "WRCP25",
        "RHEL10",
        "CentOS10",
        "TALOS",        # second Talos
    ]

    os_choice = order[idx % len(order)]

    if os_choice == "Ubuntu-22":
        return ("Ubuntu", "22.04 LTS", random.choice(UBUNTU_22_KERNELS))

    if os_choice == "Ubuntu-24":
        return ("Ubuntu", "24.04 LTS", random.choice(UBUNTU_24_KERNELS))

    if os_choice == "RHEL10":
        return ("Red Hat Enterprise Linux", "10", RHEL_KERNEL)

    if os_choice == "CentOS10":
        return ("CentOS Stream", "10", CENTOS_KERNEL)

    if os_choice == "WRCP24":
        return ("Wind River Linux WRCP", "24.09", WRCP_24_KERNEL)

    if os_choice == "WRCP25":
        return ("Wind River Linux WRCP", "25.09", random.choice(WRCP_25_KERNELS))

    if os_choice == "TALOS":
        return ("Talos Linux", "1.x", TALOS_KERNEL)

    # fallback
    return ("Ubuntu", "22.04 LTS", "5.15.0")
# ==========================================
# Subnets + IP Allocation Rules
# ==========================================

def create_subnets():
    """
    Creates all required subnets for Lab3216, Lab-E, and Lab G1.
    Returns a dictionary for easy reference.
    """

    subnets = {}

    # --------------------------
    # LAB3216 subnet (60 servers)
    # --------------------------
    lab3216, _ = Subnet.objects.get_or_create(
        name="Lab3216-Network",
        defaults={
            "network": "10.233.180.0/22",
            "vlan_id": 180,
            "gateway": "10.233.180.1",
            "description": "Lab3216 main compute subnet",
        },
    )
    subnets["lab3216"] = lab3216

    # --------------------------
    # LAB-E subnet A (40 servers)
    # --------------------------
    labe_a, _ = Subnet.objects.get_or_create(
        name="LabE-219",
        defaults={
            "network": "10.23.219.0/25",
            "vlan_id": 219,
            "gateway": "10.23.219.1",
            "description": "Lab-E Subnet /25",
        },
    )
    subnets["labe_a"] = labe_a

    # --------------------------
    # LAB-E subnet B
    # --------------------------
    labe_b, _ = Subnet.objects.get_or_create(
        name="LabE-27",
        defaults={
            "network": "10.23.27.0/24",
            "vlan_id": 27,
            "gateway": "10.23.27.1",
            "description": "Lab-E Subnet /24",
        },
    )
    subnets["labe_b"] = labe_b

    # --------------------------
    # LAB-G1 (small pool)
    # --------------------------
    labg1, _ = Subnet.objects.get_or_create(
        name="LabG1",
        defaults={
            "network": "10.23.219.0/25",
            "vlan_id": 219,
            "gateway": "10.23.219.1",
            "description": "Lab-G1 servers sharing LabE subnet",
        },
    )
    subnets["labg1"] = labg1

    return subnets


# ==========================================
# IP Allocation Helpers
# ==========================================

def next_ip(base_network: str, offset: int) -> str:
    """
    Given network string '10.233.180.0/22', replace last octet with offset.
    Example: offset=10 => 10.233.180.10
    """
    base = base_network.split("/")[0]
    parts = base.split(".")
    parts[-1] = str(offset)
    return ".".join(parts)


def assign_lab3216_ip(i: int, subnet: Subnet):
    """
    Returns ONLY:
        ssh_ip, status
    """

    STATIC_START = 10
    is_static = pick_weighted({True: 0.9, False: 0.1})

    if is_static:
        ssh_offset = STATIC_START + (i * 2)  # guaranteed no overlap
        ssh_ip = next_ip(subnet.network, ssh_offset)
        return ssh_ip, "allocated"

    # DHCP case
    dhcp_offset = 500 + (i * 2)
    ssh_ip = next_ip(subnet.network, dhcp_offset)
    return ssh_ip, "dhcp"






def assign_labe_ip(i: int, subnet: Subnet, static_range, dhcp_range):
    """
    Returns ONLY:
        ssh_ip, status
    """

    is_static = pick_weighted({True: 0.7, False: 0.3})

    if is_static:
        offset = static_range[0] + (i * 2)
        max_range = static_range[1] - static_range[0]

        if offset > static_range[1]:
            offset = static_range[0] + ((i * 2) % max_range)

        return next_ip(subnet.network, offset), "allocated"

    # DHCP
    max_range = dhcp_range[1] - dhcp_range[0]
    offset = dhcp_range[0] + (i * 2)

    if offset > dhcp_range[1]:
        offset = dhcp_range[0] + ((i * 2) % max_range)

    return next_ip(subnet.network, offset), "dhcp"




# ==========================================
# Hardware JSON Builders (Memory, Disks, NICs)
# ==========================================

def build_mem_details():
    slot_count = random.choice([8, 16])
    populated = random.choice([slot_count, slot_count // 2])

    dimm_sizes = [16, 32, 64]
    speed = random.choice([2666, 2933, 3200])

    dimms = []
    for s in range(populated):
        dimms.append({
            "slot": f"Dimms{ s+1 }",
            "size_gb": random.choice(dimm_sizes),
            "type": "DDR4",
            "speed_mhz": speed,
            "manufacturer": random.choice(["Samsung", "Micron", "Hynix"]),
            "part_number": f"M{random.randint(1000,9999)}A{random.randint(100,999)}",
        })

    return {
        "total_slots": slot_count,
        "populated_slots": populated,
        "dimms": dimms,
    }


def build_disk_details():
    layouts = [
        ("SSD", "SATA", 480),
        ("SSD", "NVMe", 960),
        ("HDD", "SAS", 2000),
    ]
    count = random.randint(1, 4)

    disks = []
    for d in range(count):
        t, iface, size = random.choice(layouts)
        disks.append({
            "id": f"disk{d}",
            "type": t,
            "interface": iface,
            "size_gb": size,
            "model": random.choice([
                "Samsung PM883",
                "Samsung PM9A3",
                "Intel S4510",
                "Seagate Exos",
            ]),
        })

    return {
        "controller": random.choice(["PERC H740P", "RAID9000", "NVMe-Direct", "AHCI"]),
        "disks": disks,
    }


def build_accelerator():
    """GPU / FPGA random builder."""
    if random.random() < 0.6:  # 60% have accelerators
        gpus = random.choice([
            {"model": "NVIDIA A100 40GB", "count": 1},
            {"model": "NVIDIA A10", "count": 1},
            {"model": "NVIDIA L40", "count": 2},
            {"model": "Habana Gaudi", "count": 1},
        ])
        fpga = random.choice([
            {"model": "Intel PAC D5005", "count": 1},
            None,
        ])
        return {
            "gpu": gpus,
            "fpga": fpga,
        }
    return None


def build_nics():
    """Realistic NIC naming patterns."""
    nic_prefixes = ["ens3f0", "ens3f1", "p1p1", "p1p2", "eth0", "eth1"]
    interfaces = []
    for n in nic_prefixes:
        interfaces.append({
            "name": n,
            "mac": mac_from_index(random.randint(10, 200)),
            "speed_gbps": random.choice([1, 10, 25, 40]),
            "type": "ethernet",
        })
    return {"interfaces": interfaces}


def build_pcie():
    slot_count = random.choice([2, 3, 4])
    slots = []
    for i in range(slot_count):
        slot_name = f"PCIe{i+1}"
        occupied = random.random() < 0.5
        slots.append({
            "slot": slot_name,
            "type": random.choice(["x8", "x16"]),
            "occupied": occupied,
            "device": random.choice(
                ["NVIDIA A10", "Dual-10Gb NIC", "Quad-1Gb NIC", None] if occupied else [None]
            ),
        })
    return {"slots": slots}


def build_user_folders(hostname):
    """Simple user folder builder."""
    return {
        "home": f"/home/{hostname}",
        "users": [
            {"user": "devops", "path": f"/home/devops"},
            {"user": "monitor", "path": f"/home/monitor"},
        ],
    }


def build_misc():
    return {
        "service_tag": f"{random.randint(1000000,9999999)}",
        "warranty": f"ProSupport until {random.randint(2025,2030)}-12-31",
        "comment": random.choice([
            "seeded record",
            "XRAN testing platform",
            "Prototype hardware",
            "Internal R&D unit",
        ]),
    }
# ==========================================
# Manufacturer / Platform / CPU Mapping
# ==========================================

MANUFACTURER_MODELS = {
    "Dell": [
        ("PowerEdge R740", ["Intel Xeon 6338N", "Intel Xeon 6338", "Intel Xeon 8360Y"], 32),
        ("PowerEdge R750", ["Intel Xeon 6248", "Intel Xeon 6240R", "Intel Xeon 6252"], 20),
        ("8620T Blade", ["Intel Xeon 6421N", "Intel Xeon 6433N"], 32),
        ("8720T Blade", ["Intel Xeon 6700P", "Intel Xeon 6709P"], 40),
    ],

    "HPE": [
        ("HPE Edgeline EL930t", ["Intel Xeon 6421N", "Intel Xeon 6443N"], 32),
        ("HPE Edgeline EL920t", ["Intel Xeon 6338", "Intel Xeon 6433N"], 32),
        ("HPE ProLiant DL380", ["Intel Xeon 6240R", "Intel Xeon 6252"], 24),
    ],

    "Quanta": [
        ("Quanta EGX77I-1U2N", ["Intel Xeon 8360Y", "Intel Xeon 6421N"], 32),
        ("QuantaEdge EGX66Y-2U", ["Intel Xeon 6338N", "Intel Xeon 6433N"], 32),
        ("QuantaEdge EGX63IS-1U", ["Intel Xeon 6248", "Intel Xeon 6421N"], 20),
    ],

    "Intel": [
        ("Intel Server CYP", ["Intel Xeon 6338N", "Intel Xeon 6338", "Intel Xeon 8360Y"], 32),
        ("Intel Server WolfPass", ["Intel Xeon 6252", "Intel Xeon 6240R", "Intel Xeon 6248"], 24),
        ("Intel Server Archer City", ["Intel Xeon 6421N", "Intel Xeon 6433N", "Intel Xeon 6443N"], 32),
        ("Intel Server Kelseyville", ["Intel Xeon 6700P", "Intel Xeon Q5N2", "Intel Xeon AAJ2", "Intel Xeon 6709P"], 40),
    ],
}


MANUFACTURERS = list(MANUFACTURER_MODELS.keys())


# ==========================================
# Rack / U Assignment
# ==========================================

def assign_rack_and_u(lab: str):
    """
    Assigns a physical location based on lab type.
    Lab3216 -> racks 1-7, 40U or 45U
    Lab-E -> racks 1-2 or bench
    Lab-G1 -> rack 1
    """

    if lab == "Lab3216":
        rack = random.randint(1, 7)
        u_start = random.randint(1, 42)
        u_end = min(u_start + random.randint(1, 2), 45)
        return f"{rack}", f"U{u_start}-U{u_end}", "Lab3216"

    if lab == "LabE":
        if random.random() < 0.7:  # 70% in racks
            rack = random.randint(1, 2)
            u_start = random.randint(1, 42)
            u_end = min(u_start + random.randint(1, 2), 45)
            return f"{rack}", f"U{u_start}-U{u_end}", "LabE"
        return "Bench", "Bench", "LabE"

    if lab == "LabG1":
        rack = 1
        u_start = random.randint(1, 42)
        u_end = min(u_start + random.randint(1, 2), 45)
        return f"{rack}", f"U{u_start}-U{u_end}", "LabG1"

    return "0", "U0", lab


# ==========================================
# Server Base Builder
# ==========================================

def build_server_base(hostname: str, lab: str, idx: int):
    """
    Returns a dictionary with base server info.
    Manufacturer, product, cpu, memory, disk, accel, nic, pcie, etc.
    """

    manu = random.choice(MANUFACTURERS)
    model, cpu_options, default_cores = random.choice(MANUFACTURER_MODELS[manu])
    cpu = random.choice(cpu_options)

    core_count = default_cores
    sockets = 2 if core_count >= 20 else 1

    total_mem = random.choice([128, 192, 256, 320])

    rack, location, room = assign_rack_and_u(lab)

    mem_details = build_mem_details()
    disk_details = build_disk_details()
    accel = build_accelerator()
    nics = build_nics()
    pcie = build_pcie()
    misc = build_misc()
    user_folders = build_user_folders(hostname)

    os_name, os_ver, kernel = pick_os_and_kernel(idx)

    return {
        "uuid": str(uuid.uuid4()),
        "manufacture": manu,
        "product_name": model,
        "cpu": cpu,
        "core_count": core_count,
        "sockets": sockets,
        "total_mem": total_mem,
        "mem_details": mem_details,
        "disk_count": len(disk_details["disks"]),
        "disk_details": disk_details,
        "bios_version": rand_bios(),
        "bios_release_date": date(
            random.randint(2022, 2024),
            random.randint(1, 12),
            random.randint(1, 28),
        ),
        "os": os_name,
        "os_version": os_ver,
        "kernel": kernel,
        "rack": rack,
        "location": location,
        "room": room,
        "accelerator": accel,
        "network_interfaces": nics,
        "expansion_slots": pcie,
        "user_folders": user_folders,
        "misc": misc,
    }
# ==========================================
# SERVER CREATION (Lab3216, LabE, LabG1)
# ==========================================

def paired_ip(i: int, network_prefix: str):
    """
    Returns (bmc_ip, ssh_ip) using datacenter style pairing:
        BMC = odd IP
        SSH = next even IP

    Pairing pattern:
        base_offset = 10 + (i-1)*2
        BMC = prefix.(base_offset + 1)
        SSH = prefix.(base_offset + 2)
    """
    base_offset = 10 + (i - 1) * 2
    bmc_last = base_offset + 1
    ssh_last = base_offset + 2
    return (
        f"{network_prefix}.{bmc_last}",
        f"{network_prefix}.{ssh_last}",
    )


def create_servers(subnets, tags):
    servers_created = 0
    notes_created = 0

    # Clean only server data (no IPAM modifications)
    Server.objects.all().delete()
    Note.objects.all().delete()

    # -------------------------------------------------------
    # CPU Handling Helpers
    # -------------------------------------------------------
    def process_cpu(cpu_full: str):
        """Convert full CPU string into short code (e.g., Xeon 6421N → 6421N)."""
        return cpu_full.split()[-1]

    def cpu_category(cpu_short: str):
        """If CPU looks like Intel Xeon (numeric prefix), set category = Server."""
        if cpu_short[0] in ("6", "8"):  # Xeon families
            return Category.objects.get(device_type="Server")
        return None

    # -------------------------------------------------------
    #  L A B  3 2 1 6 (60 servers)
    # -------------------------------------------------------
    lab3216 = subnets["lab3216"]

    for i in range(1, 61):
        hostname = f"lab3216-{i:03d}"

        base = build_server_base(hostname, "Lab3216", i)

        # CPU short name + category enforcement
        cpu_short = process_cpu(base["cpu"])
        base["cpu"] = cpu_short
        category_obj = cpu_category(cpu_short)

        # PAIRED IP LOGIC — Lab3216 uses 10.233.181.x for BMC + SSH
        bmc_ip, ssh_ip = paired_ip(i, "10.233.181")

        s = Server.objects.create(
            hostname=hostname,
            ip_address=ssh_ip,
            nic_mac=mac_from_index(i),
            bmc_ip=bmc_ip,
            bmc_mac=mac_from_index(500 + i),
            status="active",
            assign_to="ops-team",
            last_login="seed-script",
            data_source="import",
            category=category_obj,
            **base,
        )

        s.tags.set(random.sample(tags, random.randint(1, 3)))

        Note.objects.create(
            server=s,
            priority="medium",
            is_public=True,
            content=f"Initial seed note for {hostname}."
        )

        servers_created += 1
        notes_created += 1

    # -------------------------------------------------------
    #  L A B - E  (40 servers across two subnets)
    # -------------------------------------------------------
    labe_a = subnets["labe_a"]
    labe_b = subnets["labe_b"]

    for i in range(1, 41):
        hostname = f"labe-{i:03d}"

        base = build_server_base(hostname, "LabE", 100 + i)

        cpu_short = process_cpu(base["cpu"])
        base["cpu"] = cpu_short
        category_obj = cpu_category(cpu_short)

        # Subnet selection
        if i % 2 == 0:
            chosen_prefix = "10.23.219"
        else:
            chosen_prefix = "10.23.27"

        # PAIRED IP LOGIC — same pairing rule
        bmc_ip, ssh_ip = paired_ip(i, chosen_prefix)

        s = Server.objects.create(
            hostname=hostname,
            ip_address=ssh_ip,
            nic_mac=mac_from_index(100 + i),
            bmc_ip=bmc_ip,
            bmc_mac=mac_from_index(600 + i),
            status="active",
            assign_to="lab-team",
            last_login="seed-script",
            data_source="import",
            category=category_obj,
            **base,
        )

        s.tags.set(random.sample(tags, random.randint(1, 3)))

        Note.objects.create(
            server=s,
            priority="info",
            is_public=True,
            content=f"Lab-E server {hostname} created."
        )

        servers_created += 1
        notes_created += 1

    # -------------------------------------------------------
    #  L A B - G 1  (5 servers)  → Now uses 10.23.208.x
    # -------------------------------------------------------
    g1 = subnets["labg1"]  # your G1 subnet object still used, only pairing network changes

    for i in range(1, 6):
        hostname = f"g1-{i:03d}"

        base = build_server_base(hostname, "LabG1", 200 + i)

        cpu_short = process_cpu(base["cpu"])
        base["cpu"] = cpu_short
        category_obj = cpu_category(cpu_short)

        # NEW SUBNET for G1 pairing
        bmc_ip, ssh_ip = paired_ip(i, "10.23.208")

        s = Server.objects.create(
            hostname=hostname,
            ip_address=ssh_ip,
            nic_mac=mac_from_index(300 + i),
            bmc_ip=bmc_ip,
            bmc_mac=mac_from_index(700 + i),
            status="active",
            assign_to="ops-team",
            last_login="seed-script",
            data_source="import",
            category=category_obj,
            **base,
        )

        s.tags.set(random.sample(tags, random.randint(1, 3)))

        Note.objects.create(
            server=s,
            priority="low",
            is_public=True,
            content=f"G1 server {hostname} created."
        )

        servers_created += 1
        notes_created += 1

    # -------------------------------------------------------
    # DONE
    # -------------------------------------------------------
    return servers_created, notes_created

# ==========================================
# NETWORK GEAR CREATION (20 items)
# ==========================================

def create_network_gear(categories, tags, subnets):
    gear_created = 0

    gear_types = [
        ("Switch", ["Dell S5248F", "Arista 7050", "Cisco 9300", "Intel Tofino"]),
        ("PDU", ["APC AP8959", "Vertiv Geist", "ServerTech PRO2"]),
        ("Debug Tool", ["Serial Console", "JTAG Box", "ICE Debugger"]),
        ("NUC Platform", ["Intel NUC11", "Intel NUC12"]),
        ("Windows PC", ["Dell OptiPlex 7080", "HP Z2 Tower", "Lenovo ThinkStation"]),
    ]

    subnet_list = [subnets["lab3216"], subnets["labe_a"], subnets["labe_b"]]

    for i in range(1, 21):
        category_name, model_list = random.choice(gear_types)
        category_obj = categories[category_name]

        hostname = f"ng-{i:03d}"
        subnet = subnet_list[i % len(subnet_list)]

        ip_addr = next_ip(subnet.network, 200 + i)

        s = Server.objects.create(
            hostname=hostname,
            manufacture=category_name,
            product_name=random.choice(model_list),
            uuid=str(uuid.uuid4()),
            ip_address=ip_addr,
            nic_mac=mac_from_index(400 + i),
            os="EmbeddedOS",
            os_version="1.0",
            kernel="5.x",
            core_count=4,
            sockets=1,
            total_mem=16,
            mem_details={"slots": 2, "dimms": [{"size_gb": 8}, {"size_gb": 8}]},
            disk_count=1,
            disk_details={"disks": [{"size_gb": 256, "type": "SSD"}]},
            bios_version=rand_bios(),
            bios_release_date=date(
                random.randint(2021, 2024),
                random.randint(1, 12),
                random.randint(1, 28),
            ),
            rack="GearRack",
            location="Utility",
            room="Infra",
            status="active",
            assign_to="infra-team",
            last_login="seed-script",
            data_source="import",
            user_folders={"home": f"/home/{hostname}"},
            accelerator=None,
            network_interfaces=build_nics(),
            expansion_slots=build_pcie(),
            misc=build_misc(),
            category=category_obj,
        )

        s.tags.set(random.sample(tags, random.randint(1, 2)))

        gear_created += 1

    return gear_created



# ==========================================
# FINAL SEED FUNCTION
# ==========================================

def seed_all():
    categories = seed_categories()
    tags = seed_tags()
    subnets = create_subnets()

    server_count, note_count = create_servers(subnets, tags)
    gear_count = create_network_gear(categories, tags, subnets)

    return {
        "servers": server_count,
        "notes": note_count,
        "gear": gear_count,
    }



# ==========================================
# DJANGO COMMAND HANDLER
# ==========================================

class Command(BaseCommand):
    help = "Seeds database WITHOUT modifying IPAM."

    @transaction.atomic
    def handle(self, *args, **options):
        self.stdout.write(self.style.WARNING("Deleting existing servers, notes, categories, tags..."))

        Server.objects.all().delete()
        Note.objects.all().delete()
        Subnet.objects.all().delete()
        Category.objects.all().delete()
        Tag.objects.all().delete()

        self.stdout.write(self.style.WARNING("Rebuilding dataset..."))

        results = seed_all()

        self.stdout.write(self.style.SUCCESS("=== SEED COMPLETE ==="))
        self.stdout.write(self.style.SUCCESS(f"Servers created: {results['servers']}"))
        self.stdout.write(self.style.SUCCESS(f"Notes created: {results['notes']}"))
        self.stdout.write(self.style.SUCCESS(f"Network gear created: {results['gear']}"))
