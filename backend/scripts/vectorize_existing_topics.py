"""Vectorização retroativa de tópicos com embeddings locais via Ollama.

Estratégia em 2 fases:
  Fase 1 — gerar embeddings para conteúdos ÚNICOS (28k em vez de 45k chamadas)
  Fase 2 — atualizar todos os rows do banco usando o cache gerado

Usa nomic-embed-text (Ollama local) → sem rate-limit, sem custo de API.
CONCURRENCY e BATCH_SIZE altos por ser chamada local (~5ms/req).
"""
import asyncio
import logging
import sys
from pathlib import Path
from typing import Optional
from uuid import UUID

sys.path.append(str(Path(__file__).parent.parent))

from app.db.database import SessionLocal
from app.db import models
from app.providers.ollama_provider import OllamaProvider
from app.services.canonicalizer_service import CanonicalizerService

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(levelname)s] %(name)s: %(message)s",
)
logger = logging.getLogger("VectorizeTopics")

OLLAMA_URL = "http://ollama:11434"
EMBED_MODEL = "bge-m3"

BATCH_SIZE = 100   # bge-m3 é maior que nomic-embed-text, ligeiramente mais lento
CONCURRENCY = 20   # sem rate-limit de API


async def _enrich_one(
    content: str,
    provider: OllamaProvider,
    canonicalizer: CanonicalizerService,
    semaphore: asyncio.Semaphore,
) -> tuple[str, list[float], Optional[UUID]]:
    async with semaphore:
        if not content or not content.strip():
            raise ValueError("conteúdo vazio")
        embedding = await provider.embed_text(content, model_name=EMBED_MODEL)
        canonical, _ = await canonicalizer.canonicalize(content, embedding=embedding)
        return content, embedding, canonical.id if canonical else None


async def vectorize_all() -> None:
    provider = OllamaProvider(base_url=OLLAMA_URL)
    db = SessionLocal()
    semaphore = asyncio.Semaphore(CONCURRENCY)
    canonicalizer = CanonicalizerService(db, provider)

    # Warm-up: verifica conectividade antes de iniciar
    try:
        await provider.embed_text("ping", model_name=EMBED_MODEL)
        logger.info("Ollama OK — modelo %s disponível.", EMBED_MODEL)
    except Exception as exc:
        logger.error("Ollama indisponível: %s", exc)
        db.close()
        sys.exit(1)

    try:
        # ── Fase 0: contagem ───────────────────────────────────────────────
        total_rows = (
            db.query(models.Topico).filter(models.Topico.embedding.is_(None)).count()
        )
        if total_rows == 0:
            logger.info("Nada a fazer — todos os tópicos já têm embedding.")
            return

        unique_contents: list[str] = [
            row[0]
            for row in db.query(models.Topico.conteudo)
            .filter(models.Topico.embedding.is_(None))
            .distinct()
            .all()
        ]
        total_unique = len(unique_contents)
        logger.info(
            "Fase 1 — %d conteúdos únicos (de %d rows totais)",
            total_unique, total_rows,
        )

        # ── Fase 1: gerar embeddings dos únicos ────────────────────────────
        cache: dict[str, tuple[list[float], Optional[UUID]]] = {}
        failed_contents: set[str] = set()
        api_errors = 0

        for i in range(0, total_unique, BATCH_SIZE):
            sub_batch = unique_contents[i : i + BATCH_SIZE]
            tasks = [
                _enrich_one(c, provider, canonicalizer, semaphore)
                for c in sub_batch
            ]
            results = await asyncio.gather(*tasks, return_exceptions=True)

            for content, result in zip(sub_batch, results):
                if isinstance(result, Exception):
                    logger.error("[FAIL] '%s…': %s", content[:60], result)
                    failed_contents.add(content)
                    api_errors += 1
                else:
                    _, embedding, canon_id = result
                    cache[content] = (embedding, canon_id)

            done = min(i + BATCH_SIZE, total_unique)
            pct = 100 * done / total_unique
            logger.info(
                "Fase 1: %d/%d (%.1f%%) | ok: %d | falhas: %d",
                done, total_unique, pct, len(cache), api_errors,
            )

        matched = sum(1 for _, cid in cache.values() if cid is not None)
        logger.info(
            "Fase 1 concluída — cache: %d | canonical matches: %d | falhas: %d",
            len(cache), matched, api_errors,
        )

        # ── Fase 2: atualizar rows no banco ────────────────────────────────
        logger.info("Fase 2 — atualizando %d rows...", total_rows)
        db_updated = 0
        db_skipped = 0

        while True:
            query = db.query(models.Topico).filter(models.Topico.embedding.is_(None))
            if failed_contents:
                query = query.filter(
                    models.Topico.conteudo.not_in(list(failed_contents))
                )

            batch = query.limit(BATCH_SIZE).all()
            if not batch:
                break

            for topico in batch:
                enrichment = cache.get(topico.conteudo)
                if enrichment is None:
                    db_skipped += 1
                    failed_contents.add(topico.conteudo)
                    continue
                topico.embedding, topico.canonical_topic_id = enrichment
                db_updated += 1

            db.commit()
            logger.info(
                "Fase 2: %d/%d rows | skipped: %d", db_updated, total_rows, db_skipped
            )

    finally:
        db.close()

    logger.info(
        "Concluído — rows: %d | canonical: %d | falhas: %d (embed: %d | skip: %d)",
        db_updated,
        sum(1 for _, cid in cache.values() if cid),
        api_errors + db_skipped,
        api_errors,
        db_skipped,
    )
    if api_errors or db_skipped:
        sys.exit(1)


if __name__ == "__main__":
    asyncio.run(vectorize_all())
