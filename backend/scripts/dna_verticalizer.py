"""
dna_verticalizer.py — Ferramenta oficial de processamento do backlog de editais.

Reprocessa editais já ingeridos, extraindo o DNA 26 completo (GlobalDNA + CargoDNA)
e gravando os resultados no banco sem tocar nas matérias/tópicos existentes.

Uso:
    python backend/scripts/dna_verticalizer.py
    python backend/scripts/dna_verticalizer.py --limit 10
    python backend/scripts/dna_verticalizer.py --hash <content_hash>
    python backend/scripts/dna_verticalizer.py --dry-run
"""

import asyncio
import argparse
import logging
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from sqlalchemy.orm import Session
from app.db.database import SessionLocal
from app.db import models as db_models
from app.schemas.edital_schema import CargoIdentificado
from app.services.cargo_vitaminizer import CargoVitaminizerAgent, VitaminData
from app.services.cargo_anchor import AnchorEngine

logging.basicConfig(level=logging.INFO, format="%(asctime)s [%(levelname)s] %(name)s — %(message)s")
logger = logging.getLogger("dna_verticalizer")


def _resolve_storage(content_hash: str) -> Path | None:
    for candidate in [
        Path("backend/storage/processed") / content_hash,
        Path("storage/processed") / content_hash,
        Path("/app/storage/processed") / content_hash,
    ]:
        if candidate.exists():
            return candidate
    return None


def _update_edital_fields(edital_db: db_models.Edital, vitamin_data: VitaminData) -> None:
    info = vitamin_data.edital_info
    _SENTINEL = {"Pendente", "Não informada", None, ""}

    def _set(field: str, value):
        if value not in _SENTINEL:
            setattr(edital_db, field, value)

    _set("published_at", info.published_at)
    _set("inscription_start", info.inscription_start)
    _set("inscription_end", info.inscription_end)
    _set("payment_deadline", info.payment_deadline)
    _set("exam_cities", info.exam_cities)
    _set("data_prova", info.data_prova)
    if info.fee and info.fee > 0.0:
        edital_db.fee = info.fee


def _update_cargo_fields(cargo_db: db_models.Cargo, vitaminado) -> None:
    _SENTINEL = {"Pendente", "Não informada", None, ""}

    def _set(field: str, value):
        if value not in _SENTINEL:
            setattr(cargo_db, field, value)

    if vitaminado.salario and vitaminado.salario > 0.0:
        cargo_db.salario = vitaminado.salario

    _set("escolaridade", vitaminado.escolaridade)
    _set("area", vitaminado.area)
    _set("atribuicoes", vitaminado.atribuicoes)
    _set("requisitos", vitaminado.requisitos)
    _set("lotation_cities", vitaminado.lotation_cities)
    _set("jornada", vitaminado.jornada)

    # Vagas: atualiza apenas se vier com valor > 0 para não sobrescrever dados existentes
    for field in ("vagas_ac", "vagas_pcd", "vagas_cr", "vagas_negros", "vagas_indigenas", "vagas_trans", "vagas_total"):
        value = getattr(vitaminado, field, None)
        if value and value != "0":
            setattr(cargo_db, field, value)

    cargo_db.status = "vitaminado"


async def process_edital(
    edital_db: db_models.Edital,
    vitaminizer: CargoVitaminizerAgent,
    anchor: AnchorEngine,
    dry_run: bool,
) -> bool:
    if not edital_db.content_hash:
        logger.warning("Edital id=%s sem content_hash — pulando.", edital_db.id)
        return False

    storage_path = _resolve_storage(edital_db.content_hash)
    if not storage_path:
        logger.warning("  Storage não encontrado: hash=%s", edital_db.content_hash[:12])
        return False

    main_md_path = storage_path / "main.md"
    main_md = main_md_path.read_text(encoding="utf-8") if main_md_path.exists() else ""

    identified_cargos = [
        CargoIdentificado(titulo=c.titulo, codigo_edital=c.codigo_edital)
        for c in edital_db.cargos
    ]

    if not identified_cargos:
        logger.info("  Edital sem cargos cadastrados — pulando.")
        return False

    cargo_contexts = anchor.anchor(
        main_md,
        [c.titulo for c in identified_cargos],
        storage_path=storage_path,
    )
    logger.info(
        "  AnchorEngine: %d/%d contextos ancorados.",
        len(cargo_contexts),
        len(identified_cargos),
    )

    vitamin_data = await vitaminizer.vitaminize(
        edital_db.content_hash,
        identified_cargos,
        cargo_contexts=cargo_contexts,
    )

    if dry_run:
        logger.info(
            "  [DRY RUN] %d cargos processados — nenhuma escrita no banco.",
            len(vitamin_data.cargos_vitaminados),
        )
        for c in vitamin_data.cargos_vitaminados:
            logger.info("    • %s | R$ %.0f | %s vagas", c.titulo, c.salario or 0, c.vagas_total)
        return True

    db = SessionLocal()
    try:
        edital_fresh = db.query(db_models.Edital).filter_by(id=edital_db.id).first()
        if not edital_fresh:
            logger.error("  Edital não encontrado no banco para id=%s", edital_db.id)
            return False

        _update_edital_fields(edital_fresh, vitamin_data)

        cargo_map = {c.titulo.lower(): c for c in edital_fresh.cargos}
        updated = 0
        for vitaminado in vitamin_data.cargos_vitaminados:
            cargo_db = cargo_map.get(vitaminado.titulo.lower())
            if not cargo_db:
                logger.warning("  ⚠️  Cargo não encontrado no DB: '%s'", vitaminado.titulo)
                continue
            _update_cargo_fields(cargo_db, vitaminado)
            updated += 1

        db.commit()
        logger.info("  ✅ %d/%d cargos vitaminados e salvos.", updated, len(identified_cargos))
        return True
    except Exception as e:
        logger.error("  ❌ Erro ao salvar edital id=%s: %s", edital_db.id, e)
        db.rollback()
        return False
    finally:
        db.close()


async def main(limit: int | None, content_hash: str | None, dry_run: bool) -> None:
    vitaminizer = CargoVitaminizerAgent()
    anchor = AnchorEngine()

    db = SessionLocal()
    try:
        query = db.query(db_models.Edital)
        if content_hash:
            query = query.filter(db_models.Edital.content_hash == content_hash)
        if limit:
            query = query.limit(limit)
        editais = query.all()
    finally:
        db.close()

    if not editais:
        logger.info("Nenhum edital encontrado com os filtros aplicados.")
        return

    logger.info("🧬 DNA Verticalizer — %d edital(is) na fila.%s",
                len(editais), " [DRY RUN]" if dry_run else "")

    ok = fail = 0
    for i, edital_db in enumerate(editais, 1):
        logger.info(
            "[%d/%d] %s (id=%s)",
            i, len(editais),
            edital_db.orgao,
            str(edital_db.id)[:8],
        )
        success = await process_edital(edital_db, vitaminizer, anchor, dry_run)
        if success:
            ok += 1
        else:
            fail += 1

    logger.info("🏁 Concluído — %d sucesso(s), %d falha(s).", ok, fail)


if __name__ == "__main__":
    parser = argparse.ArgumentParser(
        description="DNA Verticalizer — reprocessa o backlog de editais com DNA 26."
    )
    parser.add_argument("--limit", type=int, default=None,
                        help="Limite de editais a processar (padrão: todos).")
    parser.add_argument("--hash", type=str, default=None, dest="content_hash",
                        help="Processar apenas o edital com este content_hash.")
    parser.add_argument("--dry-run", action="store_true",
                        help="Simula o processamento sem gravar no banco.")
    args = parser.parse_args()

    asyncio.run(main(limit=args.limit, content_hash=args.content_hash, dry_run=args.dry_run))
