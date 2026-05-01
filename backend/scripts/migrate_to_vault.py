import os
import hvac
from dotenv import load_dotenv

# Configurações do Vault
VAULT_URL = "http://vault:8200"  # Usando nome do serviço no docker network
VAULT_TOKEN = os.getenv("VAULT_TOKEN")

def migrate_to_vault():
    load_dotenv(override=True)
    
    keys_to_migrate = [
        "GEMINI_API_KEY",
        "GROQ_API_KEY",
        "OPENROUTER_API_KEY"
    ]
    
    client = hvac.Client(url=VAULT_URL, token=VAULT_TOKEN)
    
    if not client.is_authenticated():
        print("Erro: Não foi possível autenticar no Vault.")
        return

    secrets_dict = {}
    for key in keys_to_migrate:
        val = os.getenv(key)
        if val and "your-" not in val:
            secrets_dict[key] = val
            print(f"Migrando {key}...")

    if secrets_dict:
        client.secrets.kv.v2.create_or_update_secret(
            path='estudohub',
            secret=secrets_dict,
            mount_point='kv-v2'
        )
        print("✅ Sucesso: Chaves migradas para o Vault (kv-v2/data/estudohub).")
    else:
        print("⚠️ Nenhuma chave real encontrada para migrar.")

if __name__ == "__main__":
    migrate_to_vault()
