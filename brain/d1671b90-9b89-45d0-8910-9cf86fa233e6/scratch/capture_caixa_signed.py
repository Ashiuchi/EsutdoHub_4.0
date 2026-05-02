import requests
import os
from datetime import datetime

# URLs extraídas via Navegador Industrial
URLS = [
    ("https://concursos.cesgranrio.org.br/media/gpoweb-prd-hibrido3/eventos/19/conteudos/d67ed2a6-b45e-4b01-979b-0c19e74b184f.pdf?sv=2025-01-05&se=2036-04-28T18%3A55%3A35Z&sr=c&sp=r&sig=LGNNZMSpSMWoLIC11UK%2Fzugfw4uUtntIj1%2B0MWuwPuk%3D", "2025_CAIXA_EDITAL_01_RETIFICADO.pdf"),
    ("https://concursos.cesgranrio.org.br/media/gpoweb-prd-hibrido3/eventos/19/conteudos/c9168298-8a33-4494-8700-0064b3270b43.pdf?sv=2025-01-05&se=2036-04-28T18%3A55%3A35Z&sr=c&sp=r&sig=LGNNZMSpSMWoLIC11UK%2Fzugfw4uUtntIj1%2B0MWuwPuk%3D", "2025_CAIXA_RETIFICACAO_01.pdf"),
    ("https://concursos.cesgranrio.org.br/media/gpoweb-prd-hibrido3/eventos/19/conteudos/0963aa4f-ce32-48b1-be87-dec00e99d9ec.pdf?sv=2025-01-05&se=2036-04-28T18%3A55%3A35Z&sr=c&sp=r&sig=LGNNZMSpSMWoLIC11UK%2Fzugfw4uUtntIj1%2B0MWuwPuk%3D", "2025_CAIXA_RETIFICACAO_02.pdf")
]

SAVE_DIR = "storage_k"
os.makedirs(SAVE_DIR, exist_ok=True)

headers = {
    "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/122.0.0.0 Safari/537.36"
}

for url, filename in URLS:
    print(f"Baixando {filename}...")
    try:
        resp = requests.get(url, headers=headers, stream=True, timeout=60)
        resp.raise_for_status()
        path = os.path.join(SAVE_DIR, filename)
        with open(path, 'wb') as f:
            for chunk in resp.iter_content(chunk_size=8192):
                f.write(chunk)
        print(f"Sucesso: {path}")
    except Exception as e:
        print(f"Falha ao baixar {filename}: {e}")
