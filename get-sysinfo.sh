#!/usr/bin/env bash
# get-sysinfo.sh
# Flat key:value collector — auto-elevates to root (via sudo) and writes /tmp/sysinfo.ini world-readable.

set -uo pipefail

# ------------------------
# Auto-elevate: if not root, re-exec with sudo
# ------------------------
if [ "$EUID" -ne 0 ]; then
    if command -v sudo >/dev/null 2>&1; then
        # Re-run the script as root, preserving environment (-E) so PATH etc remain usable.
        exec sudo -E bash "$0" "$@"
    else
        echo "error: must run as root or have sudo available" >&2
        exit 1
    fi
fi

# At this point we are root (EUID == 0)

OUTFILE="/tmp/sysinfo.ini"
TMPFILE=$(mktemp /tmp/sysinfo.XXXXXX)
exec 3>"$TMPFILE"

# ---------------------------------------------------------
# Helper functions
# ---------------------------------------------------------
section() {
    echo "" >&3
    echo "# ==========================================" >&3
    echo "# $1" >&3
    echo "# ==========================================" >&3
}

write() {
    echo "$1" >&3
}

# Optional helper kept if you also want to call things without sudo (we are root now)
run() {
    "$@"
}

# ---------------------------------------------------------
# START COLLECTION
# ---------------------------------------------------------
write "collected_at:$(date '+%Y-%m-%d_%H:%M:%S')"

# ---------------------
# BMC INFORMATION
# ---------------------
section "BMC INFORMATION"
if command -v ipmitool &>/dev/null; then
    for ch in 3 1; do
        out=$(ipmitool -I open lan print "$ch" 2>/dev/null || true)
        if [ -n "$out" ]; then
            CHANNEL="$ch"
            BMC_IP=$(printf '%s\n' "$out" | awk -F': ' '/IP Address[[:space:]]*: / && !/Source/ {print $2; exit}')
            BMC_MAC=$(printf '%s\n' "$out" | awk '/MAC Address/ {print toupper($4); exit}')
            break
        fi
    done
    if [ -n "${CHANNEL:-}" ] && { [ -n "${BMC_IP:-}" ] || [ -n "${BMC_MAC:-}" ]; }; then
        write "bmc_channel:${CHANNEL}"
        write "bmc_ip:${BMC_IP:-N/A}"
        write "bmc_mac:${BMC_MAC:-N/A}"
    else
        write "bmc_info:No_BMC"
    fi
else
    write "bmc_info:No_BMC"
fi

# ---------------------
# HOSTNAME & OS
# ---------------------
section "HOSTNAME & OS"
HOSTNAME=$(hostname 2>/dev/null || true)
OS=$(hostnamectl 2>/dev/null | awk -F': ' '/Operating System/ {print $2}' | tr -d ' ' || true)
KERNEL=$(hostnamectl 2>/dev/null | awk -F': ' '/Kernel/ {print $2}' | tr -d ' ' || true)
ARCH=$(hostnamectl 2>/dev/null | awk -F': ' '/Architecture/ {print $2}' | tr -d ' ' || true)
write "hostname:${HOSTNAME}"
write "os:${OS}"
write "kernel:${KERNEL}"
write "architecture:${ARCH}"

# ---------------------
# CPU
# ---------------------
section "CPU Info"
CPU_FULL=$(lscpu 2>/dev/null | awk -F': ' '/Model name/ {print $2}' | xargs || true)
CPU_MODEL=$(echo "$CPU_FULL" | grep -oE '[0-9]{4,}[A-Z]*' | head -n1 || true)
SOCKETS=$(lscpu 2>/dev/null | awk -F': ' '/Socket\(s\)/ {print $2}' | xargs || echo "")
CORES=$(lscpu 2>/dev/null | awk -F': ' '/Core\(s\) per socket/ {print $2}' | xargs || echo "")
THREADS=$(lscpu 2>/dev/null | awk -F': ' '/Thread\(s\) per core/ {print $2}' | xargs || echo "")
write "cpu_model:${CPU_MODEL:-Unknown}"
write "sockets:${SOCKETS:-0}"
write "cores_per_socket:${CORES:-0}"
write "threads_per_core:${THREADS:-0}"

# ---------------------
# BIOS
# ---------------------
section "BIOS"
BIOS_VER=$(dmidecode -t bios 2>/dev/null | awk -F': ' '/Version:/ {print $2; exit}' | xargs || true)
BIOS_DATE=$(dmidecode -t bios 2>/dev/null | awk -F': ' '/Release Date:/ {print $2; exit}' | xargs || true)
write "bios_version:${BIOS_VER}"
write "bios_date:${BIOS_DATE}"

# ---------------------
# SYSTEM
# ---------------------
section "System"
MANU=$(dmidecode -t system 2>/dev/null | awk -F': ' '/Manufacturer:/ {print $2; exit}' | xargs || true)
PROD=$(dmidecode -t system 2>/dev/null | awk -F': ' '/Product Name:/ {print $2; exit}' | xargs || true)
SERIAL=$(dmidecode -t system 2>/dev/null | awk -F': ' '/Serial Number:/ {print $2; exit}' | xargs || true)
UUID=$(dmidecode -t system 2>/dev/null | awk -F': ' '/UUID:/ {print $2; exit}' | xargs || true)
write "system_manufacturer:${MANU}"
write "product_name:${PROD}"
write "serial_number:${SERIAL}"
write "uuid:${UUID}"

# ---------------------
# MEMORY
# ---------------------
section "Memory"
TOTAL_GB=0
while read -r line; do
    SIZE=$(echo "$line" | awk '{print $2}')
    UNIT=$(echo "$line" | awk '{print toupper($3)}')
    if [ "$UNIT" = "MB" ]; then
        TOTAL_GB=$(awk -v t="$TOTAL_GB" -v s="$SIZE" 'BEGIN{printf "%.2f", t + s/1024}')
    elif [ "$UNIT" = "GB" ]; then
        TOTAL_GB=$(awk -v t="$TOTAL_GB" -v s="$SIZE" 'BEGIN{printf "%.2f", t + s}')
    fi
done < <(dmidecode -t memory 2>/dev/null | grep 'Size:' | grep -v 'No Module Installed' || true)
write "total_memory_gb:${TOTAL_GB}"

# ---------------------
# DISKS
# ---------------------
section "Disks"
DISK_COUNT=0
while read -r name size model serial; do
    [[ "$name" =~ ^loop ]] && continue
    [[ "$name" =~ ^sr ]] && continue
    clean_model=$(echo "$model" | tr -d ' ')
    clean_serial=$(echo "$serial" | tr -d ' ')
    write "disk_${name}:${clean_model}_${clean_serial}_${size}"
    ((DISK_COUNT++))
done < <(lsblk -dn -o NAME,SIZE,MODEL,SERIAL 2>/dev/null || true)
write "disk_count:${DISK_COUNT}"

# ---------------------
# NETWORK
# ---------------------
section "Network"

# Patterns to remove generic parts of descriptions
NIC_REMOVE_PATTERNS=(
    "Intel Corporation Ethernet Controller"
    "Intel Corporation Ethernet Connection"
)
NIC_SED_PATTERN=$(printf "%s|" "${NIC_REMOVE_PATTERNS[@]}" | sed 's/|$//')

# Collect and clean Ethernet device descriptions
NIC_LIST_RAW=$(lspci 2>/dev/null | grep -i 'Ethernet' | grep -ivE 'device|broadcom|virtual' | \
    awk -F': ' '{print $2}' | sed 's/(rev.*)//g' | sed 's/[[:space:]]\+/ /g' | sort || true)

if [ -z "$NIC_LIST_RAW" ]; then
    write "nics:None"
else
    # Clean up names by removing vendor boilerplate
    CLEANED_LIST=$(printf '%s\n' "$NIC_LIST_RAW" | sed -E "s/(${NIC_SED_PATTERN}) //g" | sed -E 's/^[[:space:]]+|[[:space:]]+$//g')

    # Count duplicates and format as "Nx Model"
    NIC_COUNTS=$(printf '%s\n' "$CLEANED_LIST" | sort | uniq -c | awk '{count=$1; $1=""; model=substr($0,2); printf "%sx %s\n", count, model}' )

    # Join into single comma-separated line
    NIC_LIST=$(echo "$NIC_COUNTS" | paste -sd, -)

    write "nics:${NIC_LIST}"
fi


# ---------------------
# ACCELERATOR
# ---------------------
section "Accelerator"
REMOVE_PATTERNS=(
    "Intel Corporation"
    "Red Hat, Inc."
    "Virtio network device"
    "Device"
)
SED_PATTERN=$(printf "%s|" "${REMOVE_PATTERNS[@]}" | sed 's/|$//')
ACC_LIST=$(lspci 2>/dev/null | grep -iE 'acc|accelerator' | grep -vi "virtual" | awk -F': ' '{print $2}' | \
    sed -E "s/(${SED_PATTERN}) //g" | sed -E 's/[[:space:]]+/ /g' | sort -u | paste -sd',' - || true)
write "accelerator:${ACC_LIST:-None}"

# ---------------------
# VG LISTS
# ---------------------
section "VG lists"
VG_LIST=$(vgdisplay 2>/dev/null | awk '/VG Name/ {print $3}' | xargs | sed 's/ /,/g' || true)
if [ -z "$VG_LIST" ]; then
    write "vg:None"
else
    write "vg:${VG_LIST}"
fi

# ---------------------
# LAST 3 LOGINS
# ---------------------
section "Logins"
LAST_LOGINS=""
while read -r user tty ip month day time year; do
    [[ "$user" == "reboot" || "$user" == "shutdown" ]] && continue
    if [[ -n "$user" && -n "$month" && -n "$day" && -n "$year" ]]; then
        formatted_date=$(date -d "$month $day $year" +'%d/%m/%y' 2>/dev/null || echo "")
        [[ -z "$formatted_date" ]] && continue
        [[ -z "$ip" || "$ip" == "0.0.0.0" ]] && ip="local"
        LAST_LOGINS+="${user}_${formatted_date}@${ip},"
    fi
done < <(last -F -n 20 2>/dev/null | awk '{print $1,$2,$3,$5,$6,$7,$9}' | grep -v '^$' | head -n 10 || true)
LAST_LOGINS=$(echo "$LAST_LOGINS" | sed 's/,$//' | awk -F',' '{print $1","$2","$3}')
if [[ -z "$LAST_LOGINS" ]]; then
    write "last_login:None"
else
    write "last_login:${LAST_LOGINS}"
fi

# ---------------------------------------------------------
# Finalize: move temp file to OUTFILE and make world-readable
# ---------------------------------------------------------
exec 3>&-
mv "$TMPFILE" "$OUTFILE"
chmod 644 "$OUTFILE" || true
echo "System info collected and saved to: $OUTFILE"
