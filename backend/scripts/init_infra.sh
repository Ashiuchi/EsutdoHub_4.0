#!/usr/bin/env bash
set -euo pipefail

SONAR_URL="http://localhost:9000"
VAULT_URL="http://localhost:8205"
TIMEOUT=120
INTERVAL=5

wait_for_sonarqube() {
  echo "Aguardando SonarQube ficar UP..."
  local elapsed=0
  until curl -sf "${SONAR_URL}/api/system/status" | grep -q '"status":"UP"'; do
    if [ $elapsed -ge $TIMEOUT ]; then
      echo "Timeout: SonarQube nao ficou UP em ${TIMEOUT}s" >&2
      exit 1
    fi
    echo "  SonarQube ainda nao esta UP (${elapsed}s)..."
    sleep $INTERVAL
    elapsed=$((elapsed + INTERVAL))
  done
  echo "SonarQube esta UP."
}

wait_for_vault() {
  echo "Aguardando Vault ficar pronto..."
  local elapsed=0
  until curl -s "${VAULT_URL}/v1/sys/health" -o /dev/null 2>&1; do
    if [ $elapsed -ge $TIMEOUT ]; then
      echo "Timeout: Vault nao ficou pronto em ${TIMEOUT}s" >&2
      exit 1
    fi
    echo "  Vault ainda nao esta pronto (${elapsed}s)..."
    sleep $INTERVAL
    elapsed=$((elapsed + INTERVAL))
  done
  echo "Vault esta pronto."
}

wait_for_sonarqube
wait_for_vault

echo "Executando setup do SonarQube..."
bash scripts/setup_sonar.sh

echo "Executando setup do Vault..."
bash scripts/setup_vault.sh

echo "Infraestrutura inicializada com sucesso."
