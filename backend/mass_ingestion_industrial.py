import logging
import sys
import asyncio
import hashlib
from pathlib import Path

from app.services.ai_service import AIService
from app.services.geometric_engine import GeometricEngine
from app.services.subtractive_service import SubtractiveAgent
from app.services.fingerprint_service import FingerprintService
from app.db.database import SessionLocal
from app.db import models

logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(levelname)s - %(message)s',
    handlers=[
        logging.FileHandler("storage/industrial_ingestion.log"),
        logging.StreamHandler(sys.stdout)
    ]
)
logger = logging.getLogger("IndustrialMoenda")

STORAGE_SOURCE = Path("/storage_k")
if not STORAGE_SOURCE.exists():
    STORAGE_SOURCE = Path("sample_editais")


async def moenda_industrial():
    logger.info("🚀 Iniciando Moenda Industrial V4.0 (Daemon Mode)")
    ai_service = AIService()
    geometric = GeometricEngine()
    subtractive = SubtractiveAgent()

    while True:
        files = sorted(list(STORAGE_SOURCE.glob("*.pdf")))
        total = len(files)
        logger.info(f"📂 Escaneando {total} arquivos em {STORAGE_SOURCE}")

        for idx, pdf_path in enumerate(files, 1):
            try:
                pdf_bytes = pdf_path.read_bytes()
                content_hash = hashlib.sha256(pdf_bytes).hexdigest()

                db = SessionLocal()
                try:
                    exists = db.query(models.Edital).filter_by(content_hash=content_hash).first()
                finally:
                    db.close()

                if exists:
                    logger.info(f"⏭️  [{idx}/{total}] Já no banco, pulando: {pdf_path.name}")
                    continue

                logger.info(f"--- [{idx}/{total}] Processando: {pdf_path.name} ---")

                md_content = geometric.document_to_markdown(str(pdf_path))
                fingerprint = FingerprintService.generate_fingerprint(pdf_bytes, md_content)
                trinity = subtractive.process(md_content)
                trinity.content_hash = content_hash
                subtractive.persist(trinity)

                result = await ai_service.process_edital(
                    content_hash=content_hash,
                    md_content=md_content,
                    fingerprint=fingerprint
                )

                if result.get("id"):
                    logger.info(f"✅ Sucesso: Edital ID {result['id']} persistido.")
                else:
                    logger.warning(f"⚠️ Aviso: Edital processado mas ID não retornado.")

                logger.info("💤 Pausa de 10s para resfriamento...")
                await asyncio.sleep(10)

            except Exception as e:
                logger.error(f"❌ Erro crítico no arquivo {pdf_path.name}: {e}")
                continue

        logger.info("💤 Ciclo completo. Aguardando 5 minutos para re-escanear...")
        await asyncio.sleep(300)


if __name__ == "__main__":
    asyncio.run(moenda_industrial())
