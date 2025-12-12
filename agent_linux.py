#!/usr/bin/env python3
"""
Overwatch Agent - System Information Collector

This script collects system information from the local machine and submits it
to the Overwatch API. It's designed to be run on servers to automatically populate
the Overwatch inventory.

Usage:
    python agent_linux.py --url http://nexhub.example.com --token YOUR_API_TOKEN

Requirements:
    - Python 3.6+ (standard library only, no external dependencies)
    - Root/sudo access for dmidecode and ipmitool
"""

import argparse
import configparser
import json
import platform
import socket
import subprocess
import sys
import urllib.request
import urllib.error
import urllib.parse
from datetime import datetime
from pathlib import Path
from typing import Any


class SystemCollector:
    """Collects system information from the local machine using dmidecode and system tools."""

    def __init__(self, config_file: str = "sys_cfg.ini"):
        """Initialize collector with optional config file for overrides."""
        self.config = self._load_config(config_file)
        self.dmidecode_cache = {}
        self._cache_dmidecode()

    @staticmethod
    def _load_config(config_file: str) -> configparser.ConfigParser:
        """Load configuration file."""
        config = configparser.ConfigParser()
        if Path(config_file).exists():
            config.read(config_file)
        return config

    def _cache_dmidecode(self) -> None:
        """Run dmidecode once and cache all outputs."""
        for dmi_type in ["bios", "system", "memory", "slot"]:
            output = self.run_command(["dmidecode", "-t", dmi_type])
            self.dmidecode_cache[dmi_type] = output

    @staticmethod
    def run_command(cmd: list[str], check: bool = False) -> str:
        """Run a shell command and return output."""
        try:
            result = subprocess.run(cmd, capture_output=True, text=True, check=check)
            return result.stdout.strip()
        except (subprocess.CalledProcessError, FileNotFoundError):
            return ""

    @staticmethod
    def get_hostname() -> str:
        """Get system hostname."""
        return socket.gethostname()

    @staticmethod
    def get_ip_address() -> str | None:
        """Get primary IP address."""
        try:
            s = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
            s.connect(("8.8.8.8", 80))
            ip = s.getsockname()[0]
            s.close()
            return ip
        except Exception:
            return None

    def get_bmc_info(self) -> dict[str, Any]:
        """Get BMC information using ipmitool."""
        bmc_info = {
            "bmc_ip": "0.0.0.0",  # Default when not detected
            "bmc_mac": "00:00:00:00:00:00",  # Default when not detected
        }
        
        # Check if ipmitool is available
        if not subprocess.run(["which", "ipmitool"], capture_output=True).returncode == 0:
            return bmc_info
        
        # Try channels 3 and 1
        for channel in [3, 1]:
            output = self.run_command(["ipmitool", "-I", "open", "lan", "print", str(channel)])
            if output:
                for line in output.split("\n"):
                    if "IP Address" in line and "Source" not in line:
                        ip = line.split(":", 1)[1].strip()
                        if ip and ip != "0.0.0.0":
                            bmc_info["bmc_ip"] = ip
                    elif "MAC Address" in line:
                        mac = line.split(":", 1)[1].strip().upper()
                        if mac and mac != "00:00:00:00:00:00":
                            bmc_info["bmc_mac"] = mac
                if bmc_info["bmc_ip"] != "0.0.0.0":
                    break
        
        return bmc_info

    def get_os_info(self) -> dict[str, Any]:
        """Get operating system information using hostnamectl."""
        os_info = {}
        output = self.run_command(["hostnamectl"])
        
        for line in output.split("\n"):
            if "Operating System:" in line:
                # Extract full OS info
                full_os = line.split(":", 1)[1].strip()
                # Parse "Ubuntu 24.04.3 LTS" format
                parts = full_os.split()
                if len(parts) >= 1:
                    os_info["os"] = parts[0]  # "Ubuntu"
                    if len(parts) >= 2:
                        # Join remaining parts as version (e.g., "24.04.3 LTS")
                        os_info["os_version"] = " ".join(parts[1:])
            elif "Kernel:" in line:
                # Extract just kernel version (e.g., "6.8.0-71-generic")
                kernel_full = line.split(":", 1)[1].strip()
                # Remove leading "Linux" if present
                if kernel_full.startswith("Linux "):
                    kernel_full = kernel_full[6:]  # Remove "Linux "
                os_info["kernel"] = kernel_full
        
        # Fallback to platform module if hostnamectl fails
        if not os_info:
            os_info = {
                "os": platform.system(),
                "os_version": platform.release(),
                "kernel": platform.version().split()[0] if platform.version() else "Unknown",
            }
        
        return os_info

    @staticmethod
    def _clean_cpu_model(cpu_model: str) -> str:
        """Clean up CPU model string by removing redundant information."""
        if not cpu_model:
            return cpu_model
        
        # Remove common redundant patterns
        cpu_model = cpu_model.replace("(R)", "")
        cpu_model = cpu_model.replace("(TM)", "")
        cpu_model = cpu_model.replace("(tm)", "")
        
        # Split by multiple spaces or "CPU @" to remove clock speed
        for separator in [" CPU @", "  "]:
            if separator in cpu_model:
                cpu_model = cpu_model.split(separator)[0].strip()
                break
        
        # Remove "To Be Filled By O.E.M." suffixes
        if "To Be Filled" in cpu_model:
            cpu_model = cpu_model.split("To Be Filled")[0].strip()
        
        # Remove redundant processor info (e.g., "16-Core Processor", "64-Core Processor")
        import re
        cpu_model = re.sub(r'\s+\d+-Core\s+Processor$', '', cpu_model, flags=re.IGNORECASE)
        cpu_model = re.sub(r'\s+\d+-Core$', '', cpu_model, flags=re.IGNORECASE)
        cpu_model = re.sub(r'\s+Processor$', '', cpu_model, flags=re.IGNORECASE)
        
        # Clean up extra spaces
        cpu_model = " ".join(cpu_model.split())
        
        return cpu_model

    def get_cpu_info(self) -> dict[str, Any]:
        """Get CPU information using lscpu."""
        cpu_info = {"cpu": None, "core_count": None, "sockets": None}
        output = self.run_command(["lscpu"])
        
        for line in output.split("\n"):
            if "Model name:" in line:
                cpu_model = line.split(":", 1)[1].strip()
                # Check if CPU model is invalid (contains @0000 or is too generic)
                if "@0000" in cpu_model or "To Be Filled" in cpu_model:
                    # Use config override if available
                    config_cpu = self.config.get("hardware", "cpu", fallback="").strip()
                    cpu_info["cpu"] = self._clean_cpu_model(config_cpu if config_cpu else cpu_model)
                else:
                    cpu_info["cpu"] = self._clean_cpu_model(cpu_model)
            elif "Socket(s):" in line:
                try:
                    cpu_info["sockets"] = int(line.split(":", 1)[1].strip())
                except ValueError:
                    pass
            elif "Core(s) per socket:" in line:
                try:
                    cores_per_socket = int(line.split(":", 1)[1].strip())
                    if cpu_info["sockets"]:
                        cpu_info["core_count"] = cores_per_socket * cpu_info["sockets"]
                    else:
                        cpu_info["core_count"] = cores_per_socket
                except ValueError:
                    pass
        
        return cpu_info

    def get_bios_info(self) -> dict[str, Any]:
        """Get BIOS information from cached dmidecode."""
        bios_info = {}
        output = self.dmidecode_cache.get("bios", "")
        
        for line in output.split("\n"):
            if "Version:" in line:
                bios_info["bios_version"] = line.split(":", 1)[1].strip()
            elif "Release Date:" in line:
                date_str = line.split(":", 1)[1].strip()
                # Convert MM/DD/YYYY to YYYY-MM-DD
                try:
                    dt = datetime.strptime(date_str, "%m/%d/%Y")
                    bios_info["bios_release_date"] = dt.strftime("%Y-%m-%d")
                except ValueError:
                    # If parsing fails, skip the date
                    pass
        
        return bios_info

    def get_chassis_type(self) -> str:
        """Get chassis type from dmidecode to determine device type."""
        output = self.run_command(["dmidecode", "-t", "chassis"])
        
        # Server chassis types according to DMI specification
        server_types = {
            "Main Server Chassis", "Rack Mount Chassis", "Blade", 
            "Blade Enclosure", "Multi-system chassis", "RAID Chassis"
        }
        
        # Desktop/workstation types
        desktop_types = {
            "Desktop", "Low Profile Desktop", "Mini Tower", "Tower",
            "All in One", "Space-saving", "Pizza Box", "Compact PCI"
        }
        
        # Laptop/mobile types
        laptop_types = {
            "Laptop", "Notebook", "Sub Notebook", "Portable",
            "Hand Held", "Tablet", "Convertible", "Detachable"
        }
        
        # Other types
        embedded_types = {
            "Embedded PC", "Mini PC", "Stick PC", "IoT Gateway",
            "Sealed-case PC", "Lunch Box"
        }
        
        for line in output.split("\n"):
            if "Type:" in line:
                chassis_type = line.split(":", 1)[1].strip()
                
                # Check against known types
                if any(st in chassis_type for st in server_types):
                    return "server"
                elif any(dt in chassis_type for dt in desktop_types):
                    return "desktop"
                elif any(lt in chassis_type for lt in laptop_types):
                    return "laptop"
                elif any(et in chassis_type for et in embedded_types):
                    return "embedded"
                else:
                    # Default: try to infer from product name
                    return "other"
        
        return "other"

    def get_system_info(self) -> dict[str, Any]:
        """Get system manufacturer information from cached dmidecode."""
        system_info = {}
        output = self.dmidecode_cache.get("system", "")
        
        for line in output.split("\n"):
            if "Manufacturer:" in line:
                manufacture = line.split(":", 1)[1].strip()
                # Use config override if specified
                config_manu = self.config.get("hardware", "manufacture", fallback="").strip()
                system_info["manufacture"] = config_manu if config_manu else manufacture
            elif "Product Name:" in line:
                product = line.split(":", 1)[1].strip()
                # Use config override if specified
                config_prod = self.config.get("hardware", "product_name", fallback="").strip()
                system_info["product_name"] = config_prod if config_prod else product
            elif "UUID:" in line and "uuid" not in system_info:
                system_info["uuid"] = line.split(":", 1)[1].strip()
        
        return system_info

    def get_memory_info(self) -> dict[str, Any]:
        """Get memory information from cached dmidecode."""
        mem_info = {"total_mem": None, "mem_details": []}
        output = self.dmidecode_cache.get("memory", "")
        
        total_mb = 0
        current_module = {}
        
        for line in output.split("\n"):
            line = line.strip()
            
            if line.startswith("Memory Device"):
                if current_module and current_module.get("size") and "No Module" not in current_module.get("size", ""):
                    mem_info["mem_details"].append(current_module)
                current_module = {}
            
            if "Size:" in line and "No Module" not in line:
                size_str = line.split(":", 1)[1].strip()
                current_module["size"] = size_str
                
                # Parse size for total calculation
                parts = size_str.split()
                if len(parts) == 2:
                    try:
                        size_val = int(parts[0])
                        unit = parts[1].upper()
                        if unit == "MB":
                            total_mb += size_val
                        elif unit == "GB":
                            total_mb += size_val * 1024
                    except ValueError:
                        pass
            
            elif "Manufacturer:" in line and current_module:
                current_module["manufacturer"] = line.split(":", 1)[1].strip()
            elif "Type:" in line and current_module and "manufacturer" in current_module:
                # Only set type if we already have manufacturer (to avoid header "Type: Detail")
                mem_type = line.split(":", 1)[1].strip()
                if mem_type and mem_type != "Detail":
                    current_module["type"] = mem_type
            elif "Speed:" in line and current_module:
                current_module["speed"] = line.split(":", 1)[1].strip()
            elif "Rank:" in line and current_module:
                current_module["rank"] = line.split(":", 1)[1].strip()
        
        # Add last module
        if current_module and current_module.get("size"):
            mem_info["mem_details"].append(current_module)
        
        # Convert MB to GB
        if total_mb > 0:
            mem_info["total_mem"] = round(total_mb / 1024)
        
        return mem_info

    def get_disk_info(self) -> dict[str, Any]:
        """Get disk information using lsblk, fdisk, and df."""
        disk_info = {"disk_count": 0, "disk_details": []}
        
        # Get root mount device from df -h /
        df_root_output = self.run_command(["df", "-h", "/"])
        root_device = None
        usage_info = None
        for line in df_root_output.split("\n")[1:]:  # Skip header
            if line.strip():
                parts = line.split()
                if len(parts) >= 4:
                    # Extract the device name (e.g., /dev/mapper/ubuntu--vg-ubuntu--lv or /dev/sda1)
                    root_device = parts[0].split("/")[-1]
                    usage_info = {
                        "total": parts[1],
                        "used": parts[2],
                        "available": parts[3],
                        "usage": parts[4]
                    }
                    break
        
        # Get physical disk to partition mapping using lsblk
        lsblk_output = self.run_command(["lsblk", "-o", "NAME,SIZE,MODEL,SERIAL"])
        disk_mapping = {}  # Maps physical disk to partitions and logical volumes
        current_physical_disk = None
        current_partition = None
        
        for line in lsblk_output.split("\n"):
            if not line.strip():
                continue
            
            # Parse lsblk output (handles tree structure with ├── └── symbols)
            # First, check if line starts with tree characters to determine if it's a partition
            is_tree_line = any(c in line[:10] for c in "├└│")
            
            # Clean up tree characters
            line_clean = line
            for char in ["├", "└", "│", "─"]:
                line_clean = line_clean.replace(char, " ")
            line_clean = line_clean.strip()
            
            parts = line_clean.split(None, 3)
            
            if len(parts) >= 1:
                name = parts[0]
                
                # Skip loop and sr devices
                if name.startswith("loop") or name.startswith("sr"):
                    continue
                
                # If no tree symbols, it's a physical disk
                if not is_tree_line:
                    # Physical disk (no indentation)
                    current_physical_disk = name
                    current_partition = None
                    disk_mapping[current_physical_disk] = {
                        "size": parts[1] if len(parts) >= 2 else None,
                        "model": parts[2] if len(parts) >= 3 else None,
                        "serial": parts[3] if len(parts) >= 4 else None,
                        "partitions": []
                    }
                elif current_physical_disk:
                    # It's a partition or logical volume under current physical disk
                    disk_mapping[current_physical_disk]["partitions"].append(name)
        
        # Determine which physical disk contains the root filesystem
        root_physical_disk = None
        if root_device:
            # Search for the root device in the partition mappings
            for disk, info in disk_mapping.items():
                if root_device in info["partitions"]:
                    root_physical_disk = disk
                    break
                # Also check if root device is a direct partition
                if root_device.startswith(disk):
                    root_physical_disk = disk
                    break
        
        # Get disk information from fdisk
        fdisk_output = self.run_command(["fdisk", "-l"])
        physical_disks = {}  # Store fdisk info by disk name
        current_disk = None
        
        for line in fdisk_output.split("\n"):
            # Detect disk lines like "Disk /dev/sda: 465.76 GiB, ..."
            if line.startswith("Disk /dev/") and ":" in line:
                parts = line.split()
                if len(parts) >= 3:
                    device_path = parts[1].rstrip(":")
                    device_name = device_path.split("/")[-1]
                    
                    # Skip loop, ram, and logical volumes
                    if (device_name.startswith("loop") or 
                        device_name.startswith("ram") or 
                        device_name.startswith("dm-") or
                        "mapper" in device_path or
                        "-" in device_name):
                        current_disk = None
                        continue
                    
                    # Extract size (e.g., "465.76 GiB")
                    size = f"{parts[2]} {parts[3].rstrip(',')}" if len(parts) >= 4 else "Unknown"
                    
                    current_disk = device_name
                    physical_disks[current_disk] = {
                        "size": size,
                        "model": None
                    }
            
            # Detect model line like "Disk model: Samsung SSD 850"
            elif line.startswith("Disk model:") and current_disk:
                model = line.split(":", 1)[1].strip()
                physical_disks[current_disk]["model"] = model
        
        # Build final disk details list
        for disk_name, fdisk_info in physical_disks.items():
            disk = {
                "name": disk_name,
                "size": fdisk_info["size"]
            }
            
            if fdisk_info["model"]:
                disk["model"] = fdisk_info["model"]
            
            # Add usage info only to the disk that contains root filesystem
            if root_physical_disk and disk_name == root_physical_disk and usage_info:
                disk["usage"] = usage_info["usage"]
                disk["used"] = usage_info["used"]
                disk["available"] = usage_info["available"]
            
            disk_info["disk_details"].append(disk)
            disk_info["disk_count"] += 1
        
        return disk_info

    def get_expansion_slots_info(self) -> dict[str, Any]:
        """Get expansion slot information from cached dmidecode."""
        slots_info = {"expansion_slots": []}
        output = self.dmidecode_cache.get("slot", "")
        
        current_slot = {}
        
        for line in output.split("\n"):
            line_stripped = line.strip()
            
            # Detect start of a new slot entry
            if line_stripped.startswith("System Slot Information"):
                if current_slot:
                    # Save previous slot if it has the required fields
                    if current_slot.get("designation"):
                        slots_info["expansion_slots"].append(current_slot)
                current_slot = {}
            
            # Extract relevant fields
            if "Designation:" in line:
                current_slot["designation"] = line.split(":", 1)[1].strip()
            elif "Type:" in line:
                current_slot["type"] = line.split(":", 1)[1].strip()
            elif "Current Usage:" in line:
                current_slot["current_usage"] = line.split(":", 1)[1].strip()
            elif "ID:" in line:
                try:
                    current_slot["id"] = int(line.split(":", 1)[1].strip())
                except ValueError:
                    pass
            elif "Bus Address:" in line:
                current_slot["bus_address"] = line.split(":", 1)[1].strip()
        
        # Add last slot if it has data
        if current_slot and current_slot.get("designation"):
            slots_info["expansion_slots"].append(current_slot)
        
        return slots_info

    def get_network_interfaces_info(self) -> dict[str, Any]:
        """Get network interfaces using lspci."""
        network_info = {"network_interfaces": []}
        output = self.run_command(["lspci"])
        
        for line in output.split("\n"):
            # Case-insensitive search for network-related keywords
            line_lower = line.lower()
            if any(keyword in line_lower for keyword in ["ethernet", "network", "wireless", "wi-fi", "wifi"]):
                # Parse the PCI address and device description
                parts = line.split(None, 1)
                if len(parts) >= 2:
                    pci_address = parts[0]
                    description = parts[1]
                    network_info["network_interfaces"].append({
                        "pci_address": pci_address,
                        "description": description
                    })
        
        return network_info

    def get_accelerator_info(self) -> dict[str, Any]:
        """Get accelerator information using lspci."""
        accelerator_info = {"accelerator": []}
        output = self.run_command(["lspci"])
        
        for line in output.split("\n"):
            # Case-insensitive search for accelerator-related keywords
            line_lower = line.lower()
            if any(keyword in line_lower for keyword in ["vga", "3d", "display", "gpu", "graphics", "accelerator", "processing unit"]):
                # Parse the PCI address and device description
                parts = line.split(None, 1)
                if len(parts) >= 2:
                    pci_address = parts[0]
                    description = parts[1]
                    accelerator_info["accelerator"].append({
                        "pci_address": pci_address,
                        "description": description
                    })
        
        return accelerator_info

    def get_network_info(self) -> dict[str, Any]:
        """Get primary network interface MAC address."""
        try:
            import uuid
            mac = ":".join(["{:02x}".format((uuid.getnode() >> i) & 0xFF) for i in range(0, 8 * 6, 8)][::-1])
            return {"nic_mac": mac}
        except Exception:
            return {}

    def collect_all(self) -> dict[str, Any]:
        """Collect all system information."""
        data = {
            "hostname": self.get_hostname(),
            "ip_address": self.get_ip_address(),
            "data_source": "api",
        }

        # Add BMC info (always include, defaults to 0.0.0.0 and 00:00:00:00:00:00 if not detected)
        data.update(self.get_bmc_info())

        # Add OS info (always override)
        data.update(self.get_os_info())

        # Add CPU info (always override)
        data.update(self.get_cpu_info())

        # Add BIOS info (always override)
        data.update(self.get_bios_info())

        # Add System info (always override)
        data.update(self.get_system_info())
        
        # Add device type detection
        data["device_type"] = self.get_chassis_type()

        # Add memory info (always override)
        data.update(self.get_memory_info())

        # Add disk info (always override)
        data.update(self.get_disk_info())

        # Add expansion slots info (always override)
        data.update(self.get_expansion_slots_info())

        # Add network interfaces info (always override)
        data.update(self.get_network_interfaces_info())

        # Add accelerator info (always override)
        data.update(self.get_accelerator_info())

        # Add network info
        data.update(self.get_network_info())

        # Remove None values
        return {k: v for k, v in data.items() if v is not None}


class OverwatchClient:
    """Client for interacting with Overwatch API using urllib."""

    def __init__(self, base_url: str, token: str):
        self.base_url = base_url.rstrip("/")
        self.token = token
        self.headers = {
            "Authorization": f"Token {token}",
            "Content-Type": "application/json",
        }

    def _make_request(self, url: str, method: str = "GET", data: dict[str, Any] | None = None) -> dict[str, Any]:
        """Make HTTP request using urllib."""
        request_data = None
        if data:
            request_data = json.dumps(data).encode("utf-8")

        req = urllib.request.Request(url, data=request_data, headers=self.headers, method=method)

        try:
            with urllib.request.urlopen(req) as response:
                response_data = response.read().decode("utf-8")
                return json.loads(response_data) if response_data else {}
        except urllib.error.HTTPError as e:
            error_body = e.read().decode("utf-8")
            raise Exception(f"HTTP {e.code} error: {error_body}")
        except urllib.error.URLError as e:
            raise Exception(f"Connection error: {e.reason}")

    def get_or_create_category(self, device_type: str) -> int | None:
        """Get or create category by device_type and return its ID."""
        if not device_type:
            return None
            
        categories_url = f"{self.base_url}/api/categories/"
        
        # Get all categories and search manually (filter endpoint may not work properly)
        try:
            result = self._make_request(categories_url, method="GET")
            results = result.get("results", [])
            # Search for exact match (case-insensitive)
            device_type_lower = device_type.lower()
            for cat in results:
                if cat.get("device_type", "").lower() == device_type_lower:
                    return cat["id"]
        except Exception:
            pass
        
        # Category doesn't exist, create it
        try:
            new_category = self._make_request(
                categories_url, 
                method="POST", 
                data={"device_type": device_type.title()}
            )
            return new_category.get("id")
        except Exception as e:
            # If creation fails (e.g., duplicate), try searching again
            try:
                result = self._make_request(categories_url, method="GET")
                results = result.get("results", [])
                device_type_lower = device_type.lower()
                for cat in results:
                    if cat.get("device_type", "").lower() == device_type_lower:
                        return cat["id"]
            except Exception:
                pass
        
        return None

    def submit_server(self, data: dict[str, Any]) -> dict[str, Any]:
        """Submit server data to Overwatch API."""
        url = f"{self.base_url}/api/servers/"
        
        # Handle device_type -> category conversion
        device_type = data.pop("device_type", None)
        if device_type:
            category_id = self.get_or_create_category(device_type)
            if category_id:
                data["category"] = category_id

        # Check if server already exists by UUID (unique identifier)
        uuid = data.get("uuid")
        if uuid:
            # Use direct UUID lookup instead of search for exact matching
            search_url = f"{url}?uuid={uuid}"
            try:
                result = self._make_request(search_url, method="GET")
                results = result.get("results", [])
                if results:
                    # Server exists, update it
                    server_id = results[0]["id"]
                    update_url = f"{url}{server_id}/"
                    return self._make_request(update_url, method="PATCH", data=data)
            except Exception:
                # If search fails, try to create
                pass

        # Server doesn't exist, create it
        return self._make_request(url, method="POST", data=data)


def write_log(log_file: str, entry: dict[str, Any]) -> None:
    """Write log entry to file."""
    try:
        log_dir = Path(log_file).parent
        log_dir.mkdir(parents=True, exist_ok=True)
        
        with open(log_file, "a") as f:
            f.write(json.dumps(entry) + "\n")
    except Exception as e:
        print(f"Warning: Could not write to log file {log_file}: {e}")


def main():
    parser = argparse.ArgumentParser(description="Overwatch Agent - System Information Collector")
    parser.add_argument("--url", required=True, help="Overwatch base URL (e.g., http://localhost:8000)")
    parser.add_argument("--token", required=True, help="API authentication token")
    parser.add_argument("--dry-run", action="store_true", help="Print collected data without submitting")
    parser.add_argument("--verbose", "-v", action="store_true", help="Verbose output")
    parser.add_argument("--log-file", default="/var/log/overwatch-agent.log", help="Log file path (default: /var/log/overwatch-agent.log)")
    parser.add_argument("--config", default="sys_cfg.ini", help="Configuration file path (default: sys_cfg.ini)")

    args = parser.parse_args()

    # Setup logging
    log_entry = {
        "timestamp": datetime.now().isoformat(),
        "action": "collect",
        "hostname": socket.gethostname(),
    }

    # Collect system information
    print("Collecting system information...")
    try:
        collector = SystemCollector(config_file=args.config)
        data = collector.collect_all()
        log_entry["status"] = "collected"
        log_entry["data"] = data
    except Exception as e:
        log_entry["status"] = "error"
        log_entry["error"] = str(e)
        write_log(args.log_file, log_entry)
        print(f"\n✗ Error collecting data: {e}")
        sys.exit(1)

    if args.dry_run:
        print("\n" + "=" * 80)
        print("DRY RUN MODE - DATA COLLECTION PREVIEW")
        print("=" * 80)
        print("\nCollected System Information:")
        print("-" * 80)
        
        # Print formatted output for easier reading
        print(f"\n[+] BASIC INFO:")
        print(f"   Hostname:     {data.get('hostname', 'N/A')}")
        print(f"   UUID:         {data.get('uuid', 'N/A')}")
        print(f"   IP Address:   {data.get('ip_address', 'N/A')}")
        print(f"   Device Type:  {data.get('device_type', 'N/A').title()}")
        print(f"   Manufacturer: {data.get('manufacture', 'N/A')}")
        print(f"   Product:      {data.get('product_name', 'N/A')}")
        print(f"   Serial:       {data.get('serial_number', 'N/A')}")
        
        print(f"\n[+] CPU INFO:")
        print(f"   Model:        {data.get('cpu', 'N/A')}")
        print(f"   Cores:        {data.get('core_count', 'N/A')}")
        print(f"   Sockets:      {data.get('sockets', 'N/A')}")
        
        print(f"\n[+] MEMORY:")
        total_mem = data.get('total_mem')
        if total_mem:
            print(f"   Total:        {total_mem} GB")
        else:
            print(f"   Total:        N/A")
        print(f"   Slots:        {len(data.get('mem_details', []))} populated")
        
        print(f"\n[+] DISK:")
        disk_count = len(data.get('disk_details', []))
        print(f"   Disks:        {disk_count} physical disk(s)")
        
        print(f"\n[+] NETWORK INTERFACES:")
        net_count = len(data.get('network_interfaces', []))
        print(f"   Count:        {net_count} interface(s)")
        
        print(f"\n[+] EXPANSION SLOTS:")
        slot_count = len(data.get('expansion_slots', []))
        print(f"   Count:        {slot_count} slot(s)")
        
        print(f"\n[+] ACCELERATORS:")
        acc_count = len(data.get('accelerator', []))
        print(f"   Count:        {acc_count} device(s)")
        
        if args.verbose:
            print("\n" + "=" * 80)
            print("FULL JSON DATA:")
            print("=" * 80)
            print(json.dumps(data, indent=2))
        
        print("\n" + "=" * 80)
        print("✓ Data collection successful!")
        print("  Run without --dry-run to submit this data to the API")
        print("=" * 80 + "\n")
        
        log_entry["action"] = "dry_run"
        write_log(args.log_file, log_entry)
        return
    
    if args.verbose:
        print("\nCollected data:")
        print(json.dumps(data, indent=2))

    # Submit to API
    print(f"\nSubmitting to {args.url}...")
    try:
        client = OverwatchClient(args.url, args.token)
        result = client.submit_server(data)
        log_entry["status"] = "success"
        log_entry["action"] = "submit"
        log_entry["server_id"] = result.get("id")
        log_entry["result"] = result
        write_log(args.log_file, log_entry)
        print("\n✓ Successfully submitted server data")
        if args.verbose:
            print(json.dumps(result, indent=2))
    except Exception as e:
        log_entry["status"] = "error"
        log_entry["action"] = "submit"
        log_entry["error"] = str(e)
        write_log(args.log_file, log_entry)
        print(f"\n✗ Error submitting data: {e}")
        sys.exit(1)


if __name__ == "__main__":
    main()
