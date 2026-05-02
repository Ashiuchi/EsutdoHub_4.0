"""
agente_cirurgiao.py — Agente de resgate de cargos em quarentena.

Busca cargos com status='quarentena', diagnostica falhas de extração e tenta
recuperar apenas o trecho problemático usando anchor_text ou contexto ancorado.

Uso:
    python backend/scripts/agente_cirurgiao.py
    python backend/scripts/agente_cirurgiao.py --limit 10
    python backend/scripts/agente_cirurgiao.py --dry-run
"""

import argparse
import asyncio
import logging
import re
import sys
import unicodedata
from pathlib import Path
from typing import Iterable, Optional

from pydantic import BaseModel, Field
from sqlalchemy.orm import Session, selectinload

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from app.core.config import settings
from app.db import models as db_models
from app.db.database import SessionLocal
from app.providers.base_provider import BaseLLMProvider
from app.services.cargo_anchor import AnchorEngine


LOG_PATH = Path("storage/rescue_operation.log")
SENTINELS = {None, "", "Pendente", "Não informada", "nan", "None"}
JUNK_TITLE_TERMS = ("foto", "xerox", "envelope")
VACANCY_FIELDS = (
    "vagas_ac",
    "vagas_cr",
    "vagas_pcd",
    "vagas_negros",
    "vagas_indigenas",
    "vagas_trans",
    "vagas_total",
)


class RescueMateria(BaseModel):
    nome: str
    topicos: list[str] = Field(default_factory=list)


class RescueCargo(BaseModel):
    titulo: str
    codigo_edital: Optional[str] = None
    vagas_ac: Optional[str] = None
    vagas_cr: Optional[str] = None
    vagas_pcd: Optional[str] = None
    vagas_negros: Optional[str] = None
    vagas_indigenas: Optional[str] = None
    vagas_trans: Optional[str] = None
    vagas_total: Optional[str] = None
    salario: Optional[float] = 0.0
    escolaridade: Optional[str] = None
    area: Optional[str] = None
    atribuicoes: Optional[str] = None
    requisitos: Optional[str] = None
    lotation_cities: Optional[str] = None
    jornada: Optional[str] = None
    materias: list[RescueMateria] = Field(default_factory=list)


class RescueResponse(BaseModel):
    cargo_legitimo: bool = True
    motivo: Optional[str] = None
    cargos: list[RescueCargo] = Field(default_factory=list)


def setup_logger() -> logging.Logger:
    LOG_PATH.parent.mkdir(parents=True, exist_ok=True)
    logger = logging.getLogger("agente_cirurgiao")
    logger.setLevel(logging.INFO)
    logger.handlers.clear()

    formatter = logging.Formatter("%(asctime)s [%(levelname)s] %(message)s")
    stream = logging.StreamHandler()
    stream.setFormatter(formatter)
    logger.addHandler(stream)

    file_handler = logging.FileHandler(LOG_PATH, encoding="utf-8")
    file_handler.setFormatter(formatter)
    logger.addHandler(file_handler)
    return logger


logger = setup_logger()


def _has_value(value) -> bool:
    return value not in SENTINELS and str(value).strip() not in SENTINELS


def _normalize_text(value: str) -> str:
    text = unicodedata.normalize("NFKD", value or "")
    text = "".join(ch for ch in text if not unicodedata.combining(ch))
    return text.lower().strip()


def _is_junk_title(title: Optional[str]) -> bool:
    normalized = _normalize_text(title or "")
    if len(normalized) < 5:
        return True
    return any(term in normalized for term in JUNK_TITLE_TERMS)


def _salary_missing(cargo: db_models.Cargo) -> bool:
    return cargo.salario is None or cargo.salario <= 0.0


def _vacancies_missing(cargo: db_models.Cargo) -> bool:
    return not any(_has_value(getattr(cargo, field, None)) for field in VACANCY_FIELDS)


def _diagnose(cargo: db_models.Cargo) -> list[str]:
    failures: list[str] = []
    if not cargo.materias:
        failures.append("faltam_materias")
    if _salary_missing(cargo):
        failures.append("salario_zerado")
    if _vacancies_missing(cargo):
        failures.append("vagas_nulas")
    return failures


def _build_chain() -> list[BaseLLMProvider]:
    chain: list[BaseLLMProvider] = []
    if settings.gemini_api_key:
        try:
            from app.providers.gemini_provider import GeminiProvider

            chain.append(GeminiProvider(timeout=max(settings.gemini_timeout, 30)))
        except ImportError as exc:
            logger.warning("Gemini indisponível neste ambiente: %s", exc)

    try:
        from app.providers.ollama_provider import OllamaProvider

        chain.append(OllamaProvider(timeout=max(settings.ollama_timeout, 180)))
    except ImportError as exc:
        logger.warning("OllamaProvider indisponível neste ambiente: %s", exc)
    return chain


def _resolve_storage(content_hash: Optional[str]) -> Optional[Path]:
    if not content_hash:
        return None
    for candidate in (
        Path("backend/storage/processed") / content_hash,
        Path("storage/processed") / content_hash,
        Path("/app/storage/processed") / content_hash,
    ):
        if candidate.exists():
            return candidate
    return None


def _read_main_text(storage_path: Path) -> str:
    for filename in ("main.md", "clean.md"):
        path = storage_path / filename
        if path.exists():
            return path.read_text(encoding="utf-8")
    return ""


def _context_from_anchor_text(cargo: db_models.Cargo, main_text: str) -> Optional[str]:
    anchor_text = (cargo.anchor_text or "").strip()
    if not anchor_text:
        return None

    if not main_text:
        return anchor_text[:12000]

    normalized_main = re.sub(r"\s+", " ", main_text)
    normalized_anchor = re.sub(r"\s+", " ", anchor_text)
    idx = normalized_main.lower().find(normalized_anchor[:300].lower())
    if idx < 0:
        return anchor_text[:12000]

    start = max(0, idx - 2500)
    end = min(len(normalized_main), idx + len(normalized_anchor) + 4500)
    return normalized_main[start:end]


def _build_context(cargo: db_models.Cargo, anchor: AnchorEngine) -> Optional[str]:
    storage_path = _resolve_storage(cargo.edital.content_hash if cargo.edital else None)
    main_text = _read_main_text(storage_path) if storage_path else ""

    context = _context_from_anchor_text(cargo, main_text)
    if context:
        return context

    if storage_path and main_text:
        anchored = anchor.anchor(main_text, [cargo.titulo], storage_path=storage_path)
        if anchored.get(cargo.titulo):
            return anchored[cargo.titulo][:12000]

    return None


def _prompt_targets(failures: Iterable[str]) -> str:
    targets = []
    failures = set(failures)
    if "faltam_materias" in failures:
        targets.append("MATÉRIAS")
    if "salario_zerado" in failures:
        targets.append("SALÁRIOS")
    if "vagas_nulas" in failures:
        targets.append("CARGOS/VAGAS")
    return "/".join(targets) or "CARGOS/SALÁRIOS/MATÉRIAS"


def _build_prompt(cargo: db_models.Cargo, failures: list[str], context: str) -> str:
    targets = _prompt_targets(failures)
    return f"""
Abaixo está um trecho de edital que falhou na extração automática.
Como um auditor humano, localize e extraia rigorosamente os [{targets}]
seguindo o esquema JSON padrão.

REGRAS:
- Extraia dados apenas do trecho fornecido.
- Priorize o cargo alvo: "{cargo.titulo}".
- Se o trecho trouxer código do cargo, preserve em codigo_edital.
- salario deve ser float, usando ponto decimal. Retorne 0.0 se não encontrado.
- Vagas devem ser strings exatamente como aparecem ou totais numéricos em string.
- Matérias devem conter nome e lista de tópicos. Não invente tópicos.
- Antes de extrair, julgue se "{cargo.titulo}" é um cargo legítimo de concurso.
- Se for lixo documental, metadado, anexo, lista, comprovante, foto, xerox, envelope ou não representar cargo/função, retorne cargo_legitimo=false e cargos=[].
- Se não houver dados confiáveis para o cargo alvo, mas ele parecer cargo legítimo, retorne cargo_legitimo=true e cargos=[].
- Retorne APENAS JSON válido no formato:
{{
  "cargo_legitimo": true,
  "motivo": null,
  "cargos": [
    {{
      "titulo": "Nome do cargo",
      "codigo_edital": null,
      "vagas_ac": null,
      "vagas_cr": null,
      "vagas_pcd": null,
      "vagas_negros": null,
      "vagas_indigenas": null,
      "vagas_trans": null,
      "vagas_total": null,
      "salario": 0.0,
      "escolaridade": null,
      "area": null,
      "atribuicoes": null,
      "requisitos": null,
      "lotation_cities": null,
      "jornada": null,
      "materias": [
        {{"nome": "Português", "topicos": ["Interpretação de texto"]}}
      ]
    }}
  ]
}}

TRECHO DO EDITAL:
{context[:12000]}
"""


async def _audit_with_llm(
    cargo: db_models.Cargo,
    failures: list[str],
    context: str,
) -> tuple[Optional[RescueResponse], Optional[RescueCargo]]:
    prompt = _build_prompt(cargo, failures, context)
    for provider in _build_chain():
        try:
            response = await provider.generate_json(prompt=prompt, schema=RescueResponse)
        except Exception as exc:
            logger.warning(
                "%s falhou no resgate cargo_id=%s titulo=%r: %s",
                provider.__class__.__name__,
                cargo.id,
                cargo.titulo,
                exc,
            )
            continue

        if not response.cargo_legitimo:
            return response, None

        if not response.cargos:
            return response, None

        exact = next(
            (item for item in response.cargos if item.titulo.strip().lower() == cargo.titulo.strip().lower()),
            None,
        )
        return response, exact or response.cargos[0]

    return None, None


def _apply_scalar_fields(cargo_db: db_models.Cargo, extracted: RescueCargo) -> bool:
    changed = False
    for field in (
        "codigo_edital",
        "escolaridade",
        "area",
        "atribuicoes",
        "requisitos",
        "lotation_cities",
        "jornada",
    ):
        value = getattr(extracted, field, None)
        if _has_value(value) and not _has_value(getattr(cargo_db, field, None)):
            setattr(cargo_db, field, value)
            changed = True

    if extracted.salario and extracted.salario > 0.0 and _salary_missing(cargo_db):
        cargo_db.salario = extracted.salario
        changed = True

    for field in VACANCY_FIELDS:
        value = getattr(extracted, field, None)
        if _has_value(value) and not _has_value(getattr(cargo_db, field, None)):
            setattr(cargo_db, field, str(value))
            changed = True

    return changed


def _replace_materias(db: Session, cargo_db: db_models.Cargo, materias: list[RescueMateria]) -> bool:
    valid_materias = [m for m in materias if _has_value(m.nome)]
    if not valid_materias or cargo_db.materias:
        return False

    for materia in valid_materias:
        materia_db = db_models.Materia(nome=materia.nome.strip(), cargo=cargo_db)
        db.add(materia_db)
        for topico in materia.topicos:
            if _has_value(topico):
                db.add(db_models.Topico(conteudo=topico.strip(), materia=materia_db))
    return True


def _is_rich_and_complete(cargo_db: db_models.Cargo) -> bool:
    return bool(cargo_db.materias) and not _salary_missing(cargo_db) and not _vacancies_missing(cargo_db)


def _apply_rescue(
    db: Session,
    cargo_db: db_models.Cargo,
    extracted: RescueCargo,
    dry_run: bool,
) -> tuple[bool, str]:
    changed = _apply_scalar_fields(cargo_db, extracted)
    changed = _replace_materias(db, cargo_db, extracted.materias) or changed

    if not changed:
        return False, "sem_dados_novos"

    new_status = "vitaminado" if _is_rich_and_complete(cargo_db) else "extraido"
    cargo_db.status = new_status

    if dry_run:
        db.rollback()
    else:
        db.commit()

    return True, new_status


def _delete_cargo(db: Session, cargo_db: db_models.Cargo, reason: str, dry_run: bool) -> None:
    cargo_id = cargo_db.id
    title = cargo_db.titulo
    db.delete(cargo_db)
    if dry_run:
        db.rollback()
    else:
        db.commit()
    logger.info("Eliminação cargo_id=%s titulo=%r motivo=%s", cargo_id, title, reason)


async def process_cargo(
    cargo_id: str,
    dry_run: bool,
) -> str:
    anchor = AnchorEngine()
    db = SessionLocal()
    try:
        cargo = (
            db.query(db_models.Cargo)
            .options(
                selectinload(db_models.Cargo.materias).selectinload(db_models.Materia.topicos),
                selectinload(db_models.Cargo.edital),
            )
            .filter(db_models.Cargo.id == cargo_id)
            .first()
        )
        if not cargo or cargo.status != "quarentena":
            return "observacao"

        if _is_junk_title(cargo.titulo):
            _delete_cargo(db, cargo, "titulo_lixo", dry_run=dry_run)
            return "eliminado"

        failures = _diagnose(cargo)
        logger.info("Diagnóstico cargo_id=%s titulo=%r falhas=%s", cargo.id, cargo.titulo, ",".join(failures) or "nenhuma")

        context = _build_context(cargo, anchor)
        if not context:
            logger.info("Observação cargo_id=%s titulo=%r motivo=sem_contexto_ancorado", cargo.id, cargo.titulo)
            return "observacao"

        audit, extracted = await _audit_with_llm(cargo, failures, context)
        if audit and not audit.cargo_legitimo:
            _delete_cargo(db, cargo, f"ia_cargo_ilegitimo:{audit.motivo or 'sem_motivo'}", dry_run=dry_run)
            return "eliminado"
        if not extracted:
            logger.info("Observação cargo_id=%s titulo=%r motivo=llm_sem_resgate", cargo.id, cargo.titulo)
            return "observacao"

        rescued, status = _apply_rescue(db, cargo, extracted, dry_run=dry_run)
        if rescued:
            logger.info(
                "Resgate cargo_id=%s titulo=%r status=%s materias=%d salario=%.2f vagas_total=%s",
                cargo.id,
                cargo.titulo,
                status,
                len(cargo.materias),
                cargo.salario or 0.0,
                cargo.vagas_total,
            )
        else:
            logger.info("Observação cargo_id=%s titulo=%r motivo=%s", cargo.id, cargo.titulo, status)
        return "resgatado" if rescued else "observacao"
    except Exception as exc:
        db.rollback()
        logger.exception("Erro no resgate cargo_id=%s: %s", cargo_id, exc)
        return "observacao"
    finally:
        db.close()


async def main(limit: Optional[int], dry_run: bool) -> None:
    db = SessionLocal()
    try:
        query = (
            db.query(db_models.Cargo.id)
            .filter(db_models.Cargo.status == "quarentena")
            .order_by(db_models.Cargo.titulo.asc())
        )
        if limit:
            query = query.limit(limit)
        cargo_ids = [str(row[0]) for row in query.all()]
    finally:
        db.close()

    if not cargo_ids:
        message = "Operação Concluída: 0 cargos resgatados, 0 cargos eliminados, 0 cargos mantidos em observação (Lvl 2 necessário)."
        logger.info(message)
        print(message)
        return

    logger.info("O Cirurgião iniciado: %d cargo(s) em quarentena.%s", len(cargo_ids), " [DRY RUN]" if dry_run else "")

    rescued = 0
    eliminated = 0
    observed = 0
    for index, cargo_id in enumerate(cargo_ids, start=1):
        logger.info("[%d/%d] Operando cargo_id=%s", index, len(cargo_ids), cargo_id)
        action = await process_cargo(cargo_id, dry_run=dry_run)
        if action == "resgatado":
            rescued += 1
        elif action == "eliminado":
            eliminated += 1
        else:
            observed += 1

    message = (
        f"Operação Concluída: {rescued} cargos resgatados, {eliminated} cargos eliminados, "
        f"{observed} cargos mantidos em observação (Lvl 2 necessário)."
    )
    logger.info(message)
    print(message)


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description="O Cirurgião — resgata cargos em quarentena.")
    parser.add_argument("--limit", type=int, default=None, help="Limite de cargos em quarentena a processar.")
    parser.add_argument("--dry-run", action="store_true", help="Executa sem gravar alterações no banco.")
    args = parser.parse_args()

    asyncio.run(main(limit=args.limit, dry_run=args.dry_run))
