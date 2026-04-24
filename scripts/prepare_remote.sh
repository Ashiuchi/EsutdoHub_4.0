#!/usr/bin/env bash
# Script para preparar o acesso remoto via Tailscale

# Tenta capturar o IP do Tailscale
TS_IP=$(tailscale ip -4 2>/dev/null || echo "")

if [ -z "$TS_IP" ]; then
    echo "⚠️ Tailscale não detectado ou IP não encontrado."
    echo "Usando 'localhost' como padrão."
    TS_IP="localhost"
else
    echo "✅ Tailscale detectado! IP: $TS_IP"
fi

# Cria um arquivo de ambiente para o Docker usar
echo "REMOTE_IP=$TS_IP" > .env.remote

echo ""
echo "🚀 Sistema pronto para acesso remoto!"
echo "--------------------------------------"
echo "Frontend: http://$TS_IP:3000"
echo "Backend:  http://$TS_IP:8000"
echo "Jenkins:  http://$TS_IP:8085"
echo "Vault:    http://$TS_IP:8205"
echo "Sonar:    http://$TS_IP:9000"
echo "--------------------------------------"
echo "Para subir o sistema com este IP, use:"
echo "export REMOTE_IP=$TS_IP && docker compose up -d"
