import os
import sys
import asyncio
import logging
from pathlib import Path

# Ajuste de PATH para encontrar os módulos do backend
current_dir = Path(__file__).parent.parent
sys.path.append(str(current_dir / "backend"))

from app.services.ai_service import AIService
from app.db.database import SessionLocal
from app.db import models as db_models

# Configuração de Logs
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger("RecoveryInjection")

async def check_if_exists(content_hash: str) -> bool:
    db = SessionLocal()
    try:
        exists = db.query(db_models.Edital).filter(db_models.Edital.content_hash == content_hash).first()
        return exists is not None
    finally:
        db.close()

async def run_recovery():
    logger.info("🛠️ Iniciando Recuperação de Dados (Injection Mode)")
    ai_service = AIService()
    
    processed_root = Path("storage/processed")
    if not processed_root.exists():
        logger.error("Pasta storage/processed não encontrada!")
        return

    # Listar pastas de hashes processados
    folders = [f for f in processed_root.iterdir() if f.is_dir()]
    total = len(folders)
    logger.info(f"📂 Analisando {total} pastas processadas...")

    for idx, folder in enumerate(folders, 1):
        content_hash = folder.name
        
        # 1. Pular se já estiver no banco
        if await check_if_exists(content_hash):
            continue

        logger.info(f"--- [{idx}/{total}] Injetando no banco: {content_hash} ---")
        
        try:
            # Para recuperação, o md_content não é necessário (o service lê do disco)
            # Mas passamos o main.md se existir para manter a compatibilidade
            main_md_path = folder / "main.md"
            md_content = main_md_path.read_text(encoding="utf-8") if main_md_path.exists() else ""
            
            # 2. Re-processar apenas a camada de IA (Vitaminização + Scout)
            # Como os arquivos Trinity já existem, o AIService vai usá-los automaticamente
            result = await ai_service.process_edital(
                content_hash=content_hash,
                md_content=md_content,
                fingerprint=None # Será regenerado ou mantido como nulo
            )
            
            if result.get("id"):
                logger.info(f"✅ Injeção Sucesso: Edital ID {result['id']} criado.")
            else:
                logger.warning(f"⚠️ Injeção Falhou para {content_hash}")

            # Pausa curta para não estressar o banco
            await asyncio.sleep(2)

        except Exception as e:
            logger.error(f"❌ Erro ao injetar {content_hash}: {e}")

    logger.info("🏁 Recuperação Concluída!")

if __name__ == "__main__":
    asyncio.run(run_recovery())
