#!/bin/bash

# Configuration
VAULT_CONTAINER="vault"
KEYS_FILE=".vault_keys.txt"
VAULT_ADDR_HOST="http://localhost:8205"
VAULT_INTERNAL="http://127.0.0.1:8200"

# Check if Vault container is running
if ! docker ps | grep -q "$VAULT_CONTAINER"; then
    echo "Error: Vault container is not running. Run 'make vault-up' first."
    exit 1
fi

echo "Waiting for Vault to be ready..."
MAX_RETRIES=30
RETRY_COUNT=0

while true; do
    # Try to get status using environment variable for address
    INIT_STATUS_JSON=$(docker exec -e VAULT_ADDR="$VAULT_INTERNAL" "$VAULT_CONTAINER" vault status -format=json 2>/dev/null)
    EXIT_CODE=$?
    
    # Vault returns 0 or 2 if it's reachable (initialized or sealed)
    if [ $EXIT_CODE -eq 0 ] || [ $EXIT_CODE -eq 2 ]; then
        INIT_STATUS=$(echo "$INIT_STATUS_JSON" | grep '"initialized":' | sed 's/.*"initialized":\s*\([^,]*\),.*/\1/' | tr -d '[:space:],')
        if [ "$INIT_STATUS" != "" ]; then
            break
        fi
    fi
    
    RETRY_COUNT=$((RETRY_COUNT+1))
    if [ $RETRY_COUNT -ge $MAX_RETRIES ]; then
        echo "Error: Vault timed out. Check 'docker logs $VAULT_CONTAINER'."
        exit 1
    fi
    echo "Vault not ready yet (attempt $RETRY_COUNT)..."
    sleep 2
done
echo "Vault is reachable."

# Helper function to run vault commands with env vars
run_vault() {
    docker exec -e VAULT_ADDR="$VAULT_INTERNAL" "$VAULT_CONTAINER" vault "$@"
}

# Check if Vault is initialized
INIT_STATUS=$(run_vault status -format=json 2>/dev/null | grep '"initialized":' | sed 's/.*"initialized":\s*\([^,]*\),.*/\1/' | tr -d '[:space:],')

if [ "$INIT_STATUS" == "false" ]; then
    echo "Initializing Vault..."
    INIT_OUTPUT=$(run_vault operator init -key-shares=1 -key-threshold=1 -format=json)
    echo "$INIT_OUTPUT" > "$KEYS_FILE"
    chmod 600 "$KEYS_FILE"
    echo "Vault initialized. Keys saved to $KEYS_FILE."
else
    echo "Vault already initialized."
    if [ ! -f "$KEYS_FILE" ]; then
        echo "Error: Vault is initialized but $KEYS_FILE is missing."
        exit 1
    fi
fi

# Robust extraction using sed for multiline or single line JSON
UNSEAL_KEY=$(grep -A 1 '"unseal_keys_b64"' "$KEYS_FILE" | grep '"' | tail -n 1 | sed 's/.*"\([^"]*\)".*/\1/')
ROOT_TOKEN=$(grep '"root_token"' "$KEYS_FILE" | sed 's/.*"\([^"]*\)".*/\1/')

if [ -z "$UNSEAL_KEY" ] || [ -z "$ROOT_TOKEN" ]; then
    echo "Error: Could not extract keys from $KEYS_FILE. Check file format."
    exit 1
fi

# Check if Vault is sealed
SEALED_STATUS=$(run_vault status -format=json 2>/dev/null | grep '"sealed":' | sed 's/.*"sealed":\s*\([^,]*\),.*/\1/' | tr -d '[:space:],')

if [ "$SEALED_STATUS" == "true" ]; then
    echo "Unsealing Vault..."
    run_vault operator unseal "$UNSEAL_KEY"
else
    echo "Vault is already unsealed."
fi

# Enable KV v2 secrets engine if not already enabled
if ! docker exec -e VAULT_ADDR="$VAULT_INTERNAL" -e VAULT_TOKEN="$ROOT_TOKEN" "$VAULT_CONTAINER" vault secrets list | grep -q "^secret/"; then
    echo "Enabling KV v2 secrets engine at secret/..."
    docker exec -e VAULT_ADDR="$VAULT_INTERNAL" -e VAULT_TOKEN="$ROOT_TOKEN" "$VAULT_CONTAINER" vault secrets enable -path=secret kv-v2
else
    echo "KV v2 secrets engine already enabled at secret/."
fi

# Create initial secret example
echo "Creating initial secret: secret/data/estudohub..."
docker exec -e VAULT_ADDR="$VAULT_INTERNAL" -e VAULT_TOKEN="$ROOT_TOKEN" "$VAULT_CONTAINER" \
    vault kv put secret/estudohub \
    GEMINI_API_KEY="your-api-key-here" \
    DATABASE_URL="sqlite:///./dev.db"

echo "Vault setup completed successfully!"
echo "Root Token: $ROOT_TOKEN"
echo "VAULT_ADDR=$VAULT_ADDR_HOST"
echo "Please keep $KEYS_FILE safe and do not commit it."
