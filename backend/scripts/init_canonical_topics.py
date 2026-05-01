import asyncio
import logging
import sys
from pathlib import Path

sys.path.append(str(Path(__file__).parent.parent))

from app.db.database import SessionLocal
from app.db import models
from app.providers.ollama_provider import OllamaProvider

logging.basicConfig(level=logging.INFO, format="%(asctime)s [%(levelname)s] %(name)s: %(message)s")
logger = logging.getLogger("InitCanonical")

OLLAMA_URL = "http://ollama:11434"
EMBED_MODEL = "bge-m3"

SEED_TOPICS = [
    {"name": "Língua Portuguesa", "area": "Português"},
    {"name": "Compreensão e Interpretação de Textos", "area": "Português"},
    {"name": "Emprego do Sinal Indicativo de Crase", "area": "Português"},
    {"name": "Ortografia Oficial", "area": "Português"},
    {"name": "Concordância Verbal e Nominal", "area": "Português"},
    {"name": "Matemática", "area": "Matemática"},
    {"name": "Raciocínio Lógico-Matemático", "area": "Raciocínio Lógico"},
    {"name": "Estruturas Lógicas e Proposições", "area": "Raciocínio Lógico"},
    {"name": "Direito Constitucional", "area": "Direito Constitucional"},
    {"name": "Direitos e Garantias Fundamentais", "area": "Direito Constitucional"},
    {"name": "Direito Administrativo", "area": "Direito Administrativo"},
    {"name": "Atos Administrativos", "area": "Direito Administrativo"},
    {"name": "Licitações e Contratos", "area": "Direito Administrativo"},
    {"name": "Informática", "area": "Informática"},
    {"name": "Segurança da Informação", "area": "Informática"},
    {"name": "Sistemas Operacionais", "area": "Informática"},
]


async def init_canonical() -> None:
    provider = OllamaProvider(base_url=OLLAMA_URL)
    db = SessionLocal()
    created = 0
    skipped = 0
    failed = 0

    logger.info(f"Iniciando canonização de {len(SEED_TOPICS)} tópicos...")

    try:
        for item in SEED_TOPICS:
            name = item["name"]
            exists = db.query(models.CanonicalTopic).filter_by(name=name).first()
            if exists:
                logger.info(f"[SKIP] Já existe: {name}")
                skipped += 1
                continue

            try:
                embedding = await provider.embed_text(name, model_name=EMBED_MODEL)
                topic = models.CanonicalTopic(
                    name=name,
                    area=item["area"],
                    embedding=embedding,
                )
                db.add(topic)
                db.commit()
                logger.info(f"[OK]   Criado: {name}")
                created += 1
            except Exception as e:
                db.rollback()
                logger.error(f"[FAIL] {name}: {e}")
                failed += 1
    finally:
        db.close()

    logger.info(
        f"Concluído — criados: {created}, ignorados: {skipped}, falhas: {failed}"
    )

    if failed:
        sys.exit(1)


if __name__ == "__main__":
    asyncio.run(init_canonical())
