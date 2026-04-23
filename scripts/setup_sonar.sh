#!/usr/bin/env bash
set -euo pipefail

SONAR_URL="${SONAR_HOST_URL:-http://localhost:9000}"
SONAR_ADMIN_PASS="${SONAR_ADMIN_PASSWORD:-admin}"
PROJECT_KEY="EstudoHub_4.0"
PROJECT_NAME="EstudoHub 4.0"
TOKEN_NAME="estudohub-token"
ENV_FILE="${ENV_FILE:-.env.sonar}"
MAX_WAIT=120

# ── 1. Aguardar SonarQube ────────────────────────────────────────────────────

echo "Aguardando SonarQube em ${SONAR_URL} ..."
elapsed=0
while true; do
  status=$(curl -sf "${SONAR_URL}/api/system/status" 2>/dev/null \
    | python3 -c "import sys,json; print(json.load(sys.stdin).get('status',''))" 2>/dev/null \
    || echo "")
  if [ "$status" = "UP" ]; then
    echo "SonarQube pronto."
    break
  fi
  if [ "$elapsed" -ge "$MAX_WAIT" ]; then
    echo "Timeout: SonarQube não inicializou em ${MAX_WAIT}s." >&2
    exit 1
  fi
  printf "  [%3ds] status: %s\n" "$elapsed" "${status:-sem resposta}"
  sleep 5
  elapsed=$((elapsed + 5))
done

AUTH=(-u "admin:${SONAR_ADMIN_PASS}")

# ── 2. Verificar autenticação ────────────────────────────────────────────────

echo "Verificando credenciais admin..."
auth_response=$(curl -sf "${AUTH[@]}" "${SONAR_URL}/api/authentication/validate" 2>/dev/null \
  || echo '{"valid":false}')
valid=$(echo "$auth_response" \
  | python3 -c "import sys,json; print(json.load(sys.stdin).get('valid', False))")
if [ "$valid" != "True" ]; then
  echo "Erro de autenticação. Se a senha do admin foi alterada, defina:" >&2
  echo "  export SONAR_ADMIN_PASSWORD=<nova-senha>" >&2
  exit 1
fi

# ── 3. Criar projeto se não existir ──────────────────────────────────────────

echo "Verificando projeto '${PROJECT_KEY}'..."
search=$(curl -sf "${AUTH[@]}" "${SONAR_URL}/api/projects/search?projects=${PROJECT_KEY}")
total=$(echo "$search" \
  | python3 -c "import sys,json; print(json.load(sys.stdin)['paging']['total'])")

if [ "$total" -gt 0 ]; then
  echo "Projeto já existe."
else
  echo "Criando projeto '${PROJECT_KEY}'..."
  encoded_name=$(python3 -c "import urllib.parse; print(urllib.parse.quote_plus('${PROJECT_NAME}'))")
  curl -sf "${AUTH[@]}" -X POST \
    "${SONAR_URL}/api/projects/create?project=${PROJECT_KEY}&name=${encoded_name}" > /dev/null
  echo "Projeto criado."
fi

# ── 4. Revogar token anterior e gerar novo ───────────────────────────────────

echo "Revogando token anterior '${TOKEN_NAME}' (se existir)..."
curl -s "${AUTH[@]}" -X POST \
  "${SONAR_URL}/api/user_tokens/revoke?name=${TOKEN_NAME}" > /dev/null 2>&1 || true

echo "Gerando token '${TOKEN_NAME}'..."
response=$(curl -sf "${AUTH[@]}" -X POST \
  "${SONAR_URL}/api/user_tokens/generate?name=${TOKEN_NAME}")
token=$(echo "$response" \
  | python3 -c "import sys,json; print(json.load(sys.stdin)['token'])")

if [ -z "$token" ]; then
  echo "Erro: token não retornado pela API." >&2
  exit 1
fi

# ── 5. Salvar credenciais ─────────────────────────────────────────────────────

printf "SONAR_TOKEN=%s\nSONAR_HOST_URL=%s\n" "$token" "$SONAR_URL" > "$ENV_FILE"

echo ""
echo "Setup concluído!"
echo "  Projeto : ${PROJECT_KEY}"
echo "  Token   : salvo em ${ENV_FILE}"
echo ""
echo "Execute agora:"
echo "  make test-backend && make sonar-scan"
