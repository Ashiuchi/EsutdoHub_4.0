import requests
import os
from datetime import datetime

# CONFIGURAÇÕES INDUSTRIAIS
SAVE_DIR = "K:\\estudohub_storage"
os.makedirs(SAVE_DIR, exist_ok=True)

# LISTA MESTRE DE DESCOBERTA (PÁGINAS 1-5 CESGRANRIO)
DOWNLOAD_LIST = [
    # 1. BANESE (2025)
    ("https://concursos.cesgranrio.org.br/media/gpoweb-prd-hibrido3/eventos/17/conteudos/78d1fa5a-5407-4df9-96f6-1ece63203ba1.pdf?sv=2025-01-05&se=2036-04-28T19%3A36%3A16Z&sr=c&sp=r&sig=rEZRcYlApAnAI5HJalq0k7TV8YaeWuBdahvzHconsjc%3D", "2025_CESGRANRIO_BANESE_EDITAL_ABERTURA.pdf"),
    ("https://concursos.cesgranrio.org.br/media/gpoweb-prd-hibrido3/eventos/17/conteudos/49ad3d62-56c4-4c48-9193-05dd52855b2d.pdf?sv=2025-01-05&se=2036-04-28T19%3A36%3A16Z&sr=c&sp=r&sig=rEZRcYlApAnAI5HJalq0k7TV8YaeWuBdahvzHconsjc%3D", "2025_CESGRANRIO_BANESE_RETIFICACAO_01.pdf"),
    
    # 2. BASA (2024)
    ("https://concursos.cesgranrio.org.br/media/gpoweb-prd-hibrido3/eventos/13/conteudos/0c8ca959-09f2-44d0-b87c-38e0752dbd02.pdf?sv=2025-01-05&se=2036-04-28T19%3A39%3A20Z&sr=c&sp=r&sig=%2BL8wEsbqis5B1%2FTHAO2PbHqo3nLwy%2FEJnnY2dL6%2BbSE%3D", "2024_CESGRANRIO_BASA_EDITAL_ABERTURA.pdf"),
    ("https://concursos.cesgranrio.org.br/media/gpoweb-prd-hibrido3/eventos/13/conteudos/504e1502-8047-4149-9fde-9968bcacb143.pdf?sv=2025-01-05&se=2036-04-28T19%3A39%3A20Z&sr=c&sp=r&sig=%2BL8wEsbqis5B1%2FTHAO2PbHqo3nLwy%2FEJnnY2dL6%2BbSE%3D", "2024_CESGRANRIO_BASA_RETIFICACAO_02.pdf"),
    
    # 3. BNDES (2024)
    ("https://concursos.cesgranrio.org.br/media/gpoweb-prd-hibrido3/eventos/14/conteudos/31681178-f97b-4d8e-91aa-da17cd5971eb.pdf?sv=2025-01-05&se=2036-04-28T19%3A41%3A18Z&sr=c&sp=r&sig=Bb0RkAnYmFriTj0IYhH5s%2Fy3%2BWf1mM9Vx8Ef6Fc%2BeYs%3D", "2024_CESGRANRIO_BNDES_EDITAL_ABERTURA.pdf"),
    ("https://concursos.cesgranrio.org.br/media/gpoweb-prd-hibrido3/eventos/14/conteudos/5995c99f-aef4-46f2-9387-a67cff7b29b3.pdf?sv=2025-01-05&se=2036-04-28T19%3A41%3A18Z&sr=c&sp=r&sig=Bb0RkAnYmFriTj0IYhH5s%2Fy3%2BWf1mM9Vx8Ef6Fc%2BeYs%3D", "2024_CESGRANRIO_BNDES_RETIFICACAO.pdf"),
    
    # 4. BNB (2024)
    ("https://concursos.cesgranrio.org.br/media/gpoweb-prd-hibrido3/eventos/10/conteudos/c308d1bf-bc21-49d7-a047-5c6a597976f0.pdf?sv=2025-01-05&se=2036-04-28T19%3A42%3A09Z&sr=c&sp=r&sig=%2BAQiU7N5ukFo97LjUsYjA9lqk7TwXZ4yeJEAqADdEBU%3D", "2024_CESGRANRIO_BNB_EDITAL_ABERTURA.pdf"),
    ("https://concursos.cesgranrio.org.br/media/gpoweb-prd-hibrido3/eventos/10/conteudos/a179652f-ea63-4851-b924-0355fd295166.pdf?sv=2025-01-05&se=2036-04-28T19%3A42%3A09Z&sr=c&sp=r&sig=%2BAQiU7N5ukFo97LjUsYjA9lqk7TwXZ4yeJEAqADdEBU%3D", "2024_CESGRANRIO_BNB_RETIFICACAO_03.pdf"),
    
    # 5. IPEA (2023)
    ("https://concursos.cesgranrio.org.br/media/gpoweb-prd-hibrido3/eventos/8/conteudos/797825d1-93e5-4a6c-94cc-19601334c9f1.pdf?sv=2025-01-05&se=2036-04-28T19%3A42%3A34Z&sr=c&sp=r&sig=0cXiAxxklxd4GqXf5OGLRqFOmDFwzKxSO4A1aAN0%2Brs%3D", "2023_CESGRANRIO_IPEA_EDITAL_ABERTURA.pdf"),
    
    # 6. CASA DA MOEDA (2023)
    ("https://concursos.cesgranrio.org.br/media/gpoweb-prd-hibrido3/eventos/9/conteudos/6c7be9fe-7559-4dc5-965b-8cdcf05b707a.pdf?sv=2025-01-05&se=2036-04-28T19%3A46%3A09Z&sr=c&sp=r&sig=fUKjUmEGds9Fkv%2FcvcHNgrSDybA1wSmO0n0Dp8mgvOE%3D", "2023_CESGRANRIO_CMB_EDITAL_ABERTURA.pdf"),
    
    # 7. TRANSPETRO (2023)
    ("https://transpetro.cesgranrio.org.br/media/gpoweb-prd/eventos/12/conteudos/c2fcb95b-4d67-424b-96f8-5e401a1c4cb3.pdf?sv=2021-08-06&se=2036-04-28T19%3A47%3A22Z&sr=c&sp=r&sig=c9CFnfHERP4fmcVc749QnWFrG%2FbfHLNd11W2464wLW8%3D", "2023_CESGRANRIO_TRANSPETRO_MEDIO.pdf"),
    ("https://transpetro.cesgranrio.org.br/media/gpoweb-prd/eventos/12/conteudos/e956d516-87e7-49c6-bdf2-53b431128195.pdf?sv=2021-08-06&se=2036-04-28T19%3A47%3A22Z&sr=c&sp=r&sig=c9CFnfHERP4fmcVc749QnWFrG%2FbfHLNd11W2464wLW8%3D", "2023_CESGRANRIO_TRANSPETRO_SUPERIOR.pdf")
]

headers = {
    "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/122.0.0.0 Safari/537.36"
}

print(f"Iniciando captura em massa para {SAVE_DIR}...")
for url, filename in DOWNLOAD_LIST:
    print(f"Pescando {filename}...")
    try:
        resp = requests.get(url, headers=headers, stream=True, timeout=60)
        resp.raise_for_status()
        path = os.path.join(SAVE_DIR, filename)
        with open(path, 'wb') as f:
            for chunk in resp.iter_content(chunk_size=8192):
                f.write(chunk)
        print(f"--- [FISGADO] {filename}")
    except Exception as e:
        print(f"!!! [FALHA] {filename}: {e}")

print("Pescaria em massa concluída.")
