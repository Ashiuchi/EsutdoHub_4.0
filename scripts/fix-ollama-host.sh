#!/usr/bin/env bash
# Run this after WSL2 restarts to update OLLAMA_URL with the current WSL2 IP.
# Usage: bash scripts/fix-ollama-host.sh

set -euo pipefail

WSL2_IP=$(hostname -I | awk '{print $1}')
ENV_FILE="$(dirname "$0")/../backend/.env"

if [[ -z "$WSL2_IP" ]]; then
  echo "ERROR: Could not detect WSL2 IP" >&2
  exit 1
fi

if grep -q "^OLLAMA_URL=" "$ENV_FILE"; then
  sed -i "s|^OLLAMA_URL=.*|OLLAMA_URL=http://${WSL2_IP}:11434|" "$ENV_FILE"
else
  echo "OLLAMA_URL=http://${WSL2_IP}:11434" >> "$ENV_FILE"
fi

echo "OLLAMA_URL updated → http://${WSL2_IP}:11434"
echo "Restart the backend container: docker compose restart backend"
