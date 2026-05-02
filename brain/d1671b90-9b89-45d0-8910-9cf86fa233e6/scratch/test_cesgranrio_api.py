import requests
import json

url = "https://concursos.cesgranrio.org.br/gpoweb-prd-hibrido3/eventos"
headers = {
    "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/122.0.0.0 Safari/537.36",
    "Accept": "application/json",
    "Origin": "https://concursos.cesgranrio.org.br",
    "Referer": "https://concursos.cesgranrio.org.br/portal/avaliacoes"
}

try:
    print(f"Testando API: {url}")
    resp = requests.get(url, headers=headers, timeout=30)
    print(f"Status: {resp.status_code}")
    if resp.status_code == 200:
        data = resp.json()
        print(f"Sucesso! Encontrados {len(data)} eventos.")
        # Salva o primeiro para ver a estrutura
        with open("brain/d1671b90-9b89-45d0-8910-9cf86fa233e6/scratch/cesgranrio_api_sample.json", "w") as f:
            json.dump(data[:5], f, indent=4)
    else:
        print(f"Falha: {resp.text[:200]}")
except Exception as e:
    print(f"Erro: {e}")
