#!/usr/bin/env bash

set -euo pipefail

# NexHub bulk agent deployer (shared API-key mode)
# - Copies agent_linux.py to all hosts
# - Writes the shared API key to /etc/nexhub/agent.key on each host
# - Installs a cron job to run the agent hourly
# - Performs an initial submit to verify connectivity
#
# Requirements:
# - Run on the NexHub server
# - Passwordless SSH to targets (or cached keys); passwordless sudo on targets
# - Python3 on targets
# - Set AGENT_API_KEY environment variable or update SHARED_API_KEY below
#
# Usage:
#   export AGENT_API_KEY="your-shared-secret-here"
#   agent/tools/deploy_nexhub_agents.sh -f agent/tools/servers.txt -u http://nexhub.example.com [--dry-run]
#
# servers.txt format (one per line):
#   host1
#   user@host2
#   10.0.0.3

SCRIPT_DIR=$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)
PROJECT_ROOT=$(cd "${SCRIPT_DIR}/.." && pwd)
AGENT_SRC="${PROJECT_ROOT}/agent/agent_linux.py"

INVENTORY=""
NEXHUB_URL=""
DRY_RUN=false
SSH_OPTS=(-o BatchMode=yes -o StrictHostKeyChecking=accept-new -o ConnectTimeout=8)

# Shared API key (change this or set AGENT_API_KEY env var)
SHARED_API_KEY="${AGENT_API_KEY:-change-me-shared-agent-key-internal-only}"

usage() {
  echo "Usage: $0 -f <inventory.txt> -u <NEXHUB_URL> [--dry-run]" >&2
  echo "Set AGENT_API_KEY environment variable with your shared secret." >&2
  exit 1
}

while [[ $# -gt 0 ]]; do
  case "$1" in
    -f|--file)
      INVENTORY="$2"; shift 2 ;;
    -u|--url)
      NEXHUB_URL="$2"; shift 2 ;;
    --dry-run)
      DRY_RUN=true; shift ;;
    *)
      usage ;;
  esac
done

[[ -z "${INVENTORY}" || -z "${NEXHUB_URL}" ]] && usage
[[ ! -f "${INVENTORY}" ]] && { echo "Inventory not found: ${INVENTORY}" >&2; exit 2; }
[[ ! -f "${AGENT_SRC}" ]] && { echo "agent_linux.py not found at ${AGENT_SRC}" >&2; exit 2; }

if [[ "${SHARED_API_KEY}" == "change-me-shared-agent-key-internal-only" ]]; then
  echo "WARNING: Using default API key. Set AGENT_API_KEY environment variable." >&2
fi

echo "Starting deployment to $(wc -l <"${INVENTORY}") hosts..."

while IFS= read -r HOST || [[ -n "$HOST" ]]; do
  [[ -z "${HOST}" || "${HOST}" =~ ^# ]] && continue

  echo "--- ${HOST} ---"

  # Test SSH connectivity
  set +e
  ssh "${SSH_OPTS[@]}" "${HOST}" 'echo "SSH OK"' &>/dev/null
  STATUS=$?
  set -e
  if [[ ${STATUS} -ne 0 ]]; then
    echo "[skip] SSH failed: ${HOST}" >&2
    continue
  fi

  # Deploy agent and key
  if [[ "${DRY_RUN}" != "true" ]]; then
    # 1) Copy agent
    scp "${AGENT_SRC}" "${HOST}:/tmp/agent_linux.py"
    ssh "${SSH_OPTS[@]}" "${HOST}" 'sudo mkdir -p /usr/local/bin /etc/nexhub && sudo chmod 755 /usr/local/bin && sudo mv /tmp/agent_linux.py /usr/local/bin/agent_linux.py && sudo chmod +x /usr/local/bin/agent_linux.py'
    
    # 2) Store shared API key
    ssh "${SSH_OPTS[@]}" "${HOST}" "echo '${SHARED_API_KEY}' | sudo tee /etc/nexhub/agent.key >/dev/null && sudo chmod 600 /etc/nexhub/agent.key"
    
    # 3) Install cron job (hourly)
    CRON_LINE="0 * * * * /usr/bin/python3 /usr/local/bin/agent_linux.py --url ${NEXHUB_URL} --api-key \$(cat /etc/nexhub/agent.key) >> /var/log/nexhub-agent-cron.log 2>&1"
    ssh "${SSH_OPTS[@]}" "${HOST}" "(sudo crontab -l 2>/dev/null | grep -v 'agent_linux.py' ; echo '${CRON_LINE}') | sudo crontab -"
    
    # 4) Initial submit
    echo "Running initial submit..."
    ssh "${SSH_OPTS[@]}" "${HOST}" \
      "/usr/bin/python3 /usr/local/bin/agent_linux.py --url ${NEXHUB_URL} --api-key \$(cat /etc/nexhub/agent.key) || true"
    
    echo "✓ Deployed to ${HOST}"
  else
    echo "[dry-run] would copy agent, set key, add cron, and run initial submit"
  fi

done <"${INVENTORY}"

echo "Done. All hosts should now report to ${NEXHUB_URL} hourly."
