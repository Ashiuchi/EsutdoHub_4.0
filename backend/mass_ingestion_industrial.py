import os
import time
import logging
import sys
import asyncio
import hashlib
from pathlib import Path

# Ajuste de PATH para encontrar os módulos do backend
current_dir = Path(__file__).parent.parent
sys.path.append(str(current_dir / "backend"))

from app.services.ai_service import AIService
from app.services.geometric_engine import GeometricEngine
from app.services.subtractive_service import SubtractiveAgent
from app.services.fingerprint_service import FingerprintService

# Configuração de Logs
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
    STORAGE_SOURCE = Path("sample_editais") # Fallback

async def moenda_industrial():
    logger.info("🚀 Iniciando Moenda Industrial V4.0")
    ai_service = AIService()
    geometric = GeometricEngine()
    subtractive = SubtractiveAgent()
    
    files = sorted(list(STORAGE_SOURCE.glob("*.pdf")))
    total = len(files)
    logger.info(f"📂 Encontrados {total} peixes na rede.")

    for idx, pdf_path in enumerate(files, 1):
        try:
            logger.info(f"--- [{idx}/{total}] Processando: {pdf_path.name} ---")
            
            pdf_bytes = pdf_path.read_bytes()
            content_hash = hashlib.sha256(pdf_bytes).hexdigest()
            
            # 1. Conversão Determinística
            md_content = geometric.document_to_markdown(str(pdf_path))
            
            # 2. Geração do DNA (Fingerprint)
            fingerprint = FingerprintService.generate_fingerprint(pdf_bytes, md_content)
            
            # 3. Geração da Trindade (main, data, clean)
            trinity = subtractive.process(md_content)
            trinity.content_hash = content_hash
            subtractive.persist(trinity)
            
            # 4. Ingestão Inteligente (Ancoragem + Micro-Scout)
            result = await ai_service.process_edital(
                content_hash=content_hash,
                md_content=md_content, # Passado por compatibilidade
                fingerprint=fingerprint
            )
            
            if result.get("id"):
                logger.info(f"✅ Sucesso: Edital ID {result['id']} persistido.")
            else:
                logger.warning(f"⚠️ Aviso: Edital processado mas ID não retornado (possível duplicata).")

            # Pausa Térmica (para o PC não fritar)
            logger.info("💤 Pausa de 10s para resfriamento...")
            await asyncio.sleep(10)

        except Exception as e:
            logger.error(f"❌ Erro crítico no arquivo {pdf_path.name}: {e}")
            continue

    logger.info("🏁 Moenda Industrial Concluída. Todos os peixes foram processados!")

if __name__ == "__main__":
    import sys
    asyncio.run(moenda_industrial())
