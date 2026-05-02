"""
agente_arquiteto.py - Auditor final de quarentena por tabelas do PDF.

Uso:
    python backend/scripts/agente_arquiteto.py
    python backend/scripts/agente_arquiteto.py --limit 20
    python backend/scripts/agente_arquiteto.py --dry-run
"""

import argparse
import asyncio
import hashlib
import json
import logging
import re
import sys
import unicodedata
from dataclasses import dataclass
from pathlib import Path
from typing import Optional
from urllib.parse import unquote, urlparse

from pydantic import BaseModel, Field
from sqlalchemy.exc import SQLAlchemyError
from sqlalchemy.orm import selectinload

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from app.db import models as db_models
from app.db.database import SessionLocal
from app.providers.base_provider import BaseLLMProvider

try:
    import pandas as pd
    import pdfplumber
except ImportError as exc:
    missing_dependency = exc
    pd = None
    pdfplumber = None
else:
    missing_dependency = None


LOG_PATH = Path("storage/architect_operation.log")
HASH_INDEX_PATH = Path("storage/pdf_hash_index.json")
OUTCOME_TERMS = (
    "resultado",
    "convocacao",
    "convocação",
    "isencao",
    "isenção",
    "lista de candidatos",
    "homologacao",
    "homologação",
    "gabarito",
    "inscritos",
)
OPENING_TERMS = (
    "edital de abertura",
    "concurso publico",
    "concurso público",
    "torna publica a abertura",
    "torna pública a abertura",
    "inscricoes",
    "inscrições",
)
SCAN_STATUS = "lvl2:#SCAN_SUJO"
DOU_STATUS = "lvl2:#DOU"
PDF_ROOTS = (
    Path("/storage_k"),
    Path("storage_k"),
    Path("sample_editais"),
    Path("backend"),
    Path("."),
)
FAST_PDF_ROOTS = (Path("/storage_k"), Path("storage_k"))
PROCESSED_ROOTS = (Path("storage/processed"), Path("backend/storage/processed"), Path("/app/storage/processed"))
ORG_ALIASES = {
    "ministerio_da_educacao": ("mec",),
    "ministerio_educacao": ("mec",),
}
VACANCY_FIELDS = (
    "vagas_ac",
    "vagas_cr",
    "vagas_pcd",
    "vagas_negros",
    "vagas_indigenas",
    "vagas_trans",
    "vagas_total",
)


class ColumnMapping(BaseModel):
    cargo: Optional[str] = None
    vagas: Optional[str] = None
    salario: Optional[str] = None
    escolaridade: Optional[str] = None
    confidence: float = Field(default=0.0, ge=0.0, le=1.0)
    reason: Optional[str] = None
    tags: list[str] = Field(default_factory=list)


@dataclass
class TableCandidate:
    page_number: int
    table_index: int
    dataframe: "pd.DataFrame"


@dataclass
class RescueResult:
    rescued: bool
    status: str
    reason: str


def setup_logger() -> logging.Logger:
    LOG_PATH.parent.mkdir(parents=True, exist_ok=True)
    logger = logging.getLogger("agente_arquiteto")
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


def _normalize(value: str) -> str:
    text = unicodedata.normalize("NFKD", value or "")
    text = "".join(ch for ch in text if not unicodedata.combining(ch))
    return re.sub(r"\s+", " ", text.lower()).strip()


def _compact(value: str) -> str:
    return re.sub(r"[^a-z0-9]+", "", _normalize(value))


def _has_value(value) -> bool:
    if value is None:
        return False
    text = str(value).strip()
    return bool(text) and text.lower() not in {"nan", "none", "nao informada", "não informada", "pendente"}


def _build_chain() -> list[BaseLLMProvider]:
    chain: list[BaseLLMProvider] = []
    try:
        from app.providers.ollama_provider import OllamaProvider
        from app.core.config import settings

        chain.append(OllamaProvider(model=settings.ollama_model, timeout=max(settings.ollama_timeout, 600)))
    except ImportError as exc:
        logger.warning("OllamaProvider indisponivel: %s", exc)
    return chain


def _load_hash_index() -> dict[str, str]:
    if not HASH_INDEX_PATH.exists():
        return {}
    try:
        with HASH_INDEX_PATH.open("r", encoding="utf-8") as file:
            data = json.load(file)
        return data if isinstance(data, dict) else {}
    except Exception:
        return {}


def _save_hash_index(index: dict[str, str]) -> None:
    HASH_INDEX_PATH.parent.mkdir(parents=True, exist_ok=True)
    with HASH_INDEX_PATH.open("w", encoding="utf-8") as file:
        json.dump(index, file, indent=2, ensure_ascii=False)


def _sha256_file(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as file:
        for chunk in iter(lambda: file.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def _path_from_local_link(link: Optional[str]) -> Optional[Path]:
    if not link:
        return None

    parsed = urlparse(link)
    if parsed.scheme in {"http", "https"}:
        return None

    raw_path = unquote(parsed.path if parsed.scheme == "file" else link).strip()
    if not raw_path:
        return None

    match = re.match(r"^([a-zA-Z]):[\\/](.*)$", raw_path)
    if match:
        raw_path = f"/mnt/{match.group(1).lower()}/{match.group(2).replace('\\', '/')}"

    direct = Path(raw_path).expanduser()
    if direct.exists():
        return direct

    filename = Path(raw_path).name
    for root in FAST_PDF_ROOTS:
        candidate = root / filename
        if candidate.exists():
            return candidate
    return None


def _probable_storage_hash_paths(content_hash: str) -> list[Path]:
    names = (
        f"{content_hash}.pdf",
        f"{content_hash}.PDF",
        f"temp_{content_hash}.pdf",
        f"temp_{content_hash}.PDF",
    )
    return [root / name for root in FAST_PDF_ROOTS for name in names]


def _filename_key(value: Optional[str]) -> str:
    normalized = _normalize(value or "")
    return re.sub(r"[^a-z0-9]+", "_", normalized).strip("_")


def _name_tokens(value: Optional[str]) -> list[str]:
    key = _filename_key(value)
    if not key:
        return []
    ignored = {"de", "da", "do", "das", "dos", "e", "a", "o"}
    return [token for token in key.split("_") if len(token) > 1 and token not in ignored]


def _aliases_for(value: Optional[str]) -> list[str]:
    key = _filename_key(value)
    aliases = list(ORG_ALIASES.get(key, ()))
    tokens = _name_tokens(value)
    if len(tokens) >= 2:
        aliases.append("".join(token[0] for token in tokens))
    return [alias for alias in aliases if alias]


def _processed_main_text(content_hash: Optional[str]) -> str:
    if not content_hash:
        return ""
    for root in PROCESSED_ROOTS:
        path = root / content_hash / "main.md"
        if path.exists():
            try:
                return path.read_text(encoding="utf-8", errors="ignore")
            except OSError:
                return ""
    return ""


def _token_hits(tokens: list[str], text_key: str) -> int:
    return sum(1 for token in tokens if token in text_key)


def _friendly_storage_candidates(edital: db_models.Edital) -> list[Path]:
    orgao_tokens = _name_tokens(edital.orgao)
    banca_tokens = _name_tokens(edital.banca)
    orgao_aliases = _aliases_for(edital.orgao)
    banca_aliases = _aliases_for(edital.banca)
    if not orgao_tokens and not banca_tokens and not orgao_aliases and not banca_aliases:
        return []

    candidates: list[tuple[int, Path]] = []
    for root in FAST_PDF_ROOTS:
        if not root.exists():
            continue
        for path in root.iterdir():
            if not path.is_file() or path.suffix.lower() != ".pdf":
                continue
            filename_key = _filename_key(path.stem)
            orgao_hits = _token_hits(orgao_tokens, filename_key)
            banca_hits = _token_hits(banca_tokens, filename_key)
            orgao_alias_hit = any(alias in filename_key for alias in orgao_aliases)
            banca_alias_hit = any(alias in filename_key for alias in banca_aliases)

            strong_orgao_match = bool(orgao_tokens) and (
                orgao_hits >= min(2, len(orgao_tokens)) or "_".join(orgao_tokens[:3]) in filename_key
            )
            banca_match = (
                bool(banca_tokens)
                and banca_tokens[0] not in {"desconhecida"}
                and (banca_hits > 0 or banca_alias_hit)
            )

            if strong_orgao_match or orgao_alias_hit or (banca_match and (orgao_hits > 0 or orgao_alias_hit)):
                score = orgao_hits * 10 + banca_hits
                if orgao_alias_hit:
                    score += 25
                if banca_alias_hit:
                    score += 5
                candidates.append((score, path))

    return [path for _, path in sorted(candidates, key=lambda item: item[0], reverse=True)]


def _main_confirms_candidate(edital: db_models.Edital, candidate: Path, main_text: str) -> bool:
    if not main_text:
        return False

    main_key = _filename_key(main_text[:50000])
    filename_key = _filename_key(candidate.stem)
    orgao_tokens = _name_tokens(edital.orgao)
    banca_tokens = [token for token in _name_tokens(edital.banca) if token not in {"desconhecida"}]
    orgao_aliases = _aliases_for(edital.orgao)

    orgao_in_main = _token_hits(orgao_tokens, main_key) >= min(2, len(orgao_tokens)) if orgao_tokens else False
    banca_in_main = bool(banca_tokens) and _token_hits(banca_tokens, main_key) > 0
    file_has_orgao = _token_hits(orgao_tokens, filename_key) >= min(2, len(orgao_tokens)) if orgao_tokens else False
    file_has_alias = any(alias in filename_key for alias in orgao_aliases)
    file_has_banca = bool(banca_tokens) and _token_hits(banca_tokens, filename_key) > 0

    return (orgao_in_main and (file_has_orgao or file_has_alias)) or (banca_in_main and file_has_banca and (file_has_orgao or file_has_alias))


def _friendly_name_is_strong(edital: db_models.Edital, candidate: Path) -> bool:
    filename_key = _filename_key(candidate.stem)
    orgao_tokens = _name_tokens(edital.orgao)
    banca_tokens = [token for token in _name_tokens(edital.banca) if token not in {"desconhecida"}]
    orgao_aliases = _aliases_for(edital.orgao)

    orgao_hits = _token_hits(orgao_tokens, filename_key)
    has_full_orgao = bool(orgao_tokens) and "_".join(orgao_tokens[:3]) in filename_key
    has_orgao_alias = any(alias in filename_key for alias in orgao_aliases)
    has_banca = bool(banca_tokens) and _token_hits(banca_tokens, filename_key) > 0

    return has_full_orgao or has_orgao_alias or (
        bool(orgao_tokens) and orgao_hits >= min(3, len(orgao_tokens)) and (has_banca or len(orgao_tokens) <= 3)
    )


def _candidate_pdf_paths(content_hash: Optional[str], link: Optional[str]) -> list[Path]:
    candidates: list[Path] = []
    link_path = _path_from_local_link(link)
    if link_path:
        candidates.append(link_path)

    if content_hash:
        candidates.extend(_probable_storage_hash_paths(content_hash))
        patterns = [
            f"temp_{content_hash}_*.pdf",
            f"temp_{content_hash}_*.PDF",
            f"*{content_hash}*.pdf",
            f"*{content_hash}*.PDF",
        ]
        for root in (Path("/storage_k"), Path("storage_k"), Path("."), Path("backend"), Path("/tmp")):
            if root.exists():
                for pattern in patterns:
                    candidates.extend(root.glob(pattern))

    unique: list[Path] = []
    seen = set()
    for path in candidates:
        resolved = path.resolve()
        if resolved not in seen and path.exists() and path.suffix.lower() == ".pdf":
            seen.add(resolved)
            unique.append(path)
    return unique


def resolve_pdf_path(edital: db_models.Edital, scan_storage: bool = True) -> Optional[Path]:
    content_hash = edital.content_hash
    link_path = _path_from_local_link(edital.link)
    if link_path and link_path.suffix.lower() == ".pdf":
        return link_path

    main_text = _processed_main_text(content_hash)
    for candidate in _friendly_storage_candidates(edital):
        if _main_confirms_candidate(edital, candidate, main_text):
            logger.info("PDF localizado por nome + main.md: edital_id=%s path=%s", edital.id, candidate)
            return candidate
        if _friendly_name_is_strong(edital, candidate):
            logger.info("PDF localizado por nome amigavel: edital_id=%s path=%s", edital.id, candidate)
            return candidate
        try:
            if _sha256_file(candidate) == content_hash:
                logger.info("PDF localizado por nome e confirmado por hash: edital_id=%s path=%s", edital.id, candidate)
                return candidate
        except OSError:
            continue

    for candidate in _candidate_pdf_paths(content_hash, edital.link):
        if not content_hash or _sha256_file(candidate) == content_hash:
            return candidate

    if not content_hash or not scan_storage:
        return None

    index = _load_hash_index()
    indexed = index.get(content_hash)
    if indexed and Path(indexed).exists():
        return Path(indexed)

    for root in PDF_ROOTS:
        if not root.exists():
            continue
        for path in root.rglob("*.pdf"):
            try:
                file_hash = _sha256_file(path)
            except OSError:
                continue
            index[file_hash] = str(path)
            if file_hash == content_hash:
                _save_hash_index(index)
                return path
        for path in root.rglob("*.PDF"):
            try:
                file_hash = _sha256_file(path)
            except OSError:
                continue
            index[file_hash] = str(path)
            if file_hash == content_hash:
                _save_hash_index(index)
                return path
    _save_hash_index(index)
    return None


def _first_pages_text(pdf_path: Path, max_pages: int = 3) -> str:
    with pdfplumber.open(str(pdf_path)) as pdf:
        chunks = []
        for page in pdf.pages[:max_pages]:
            chunks.append(page.extract_text(x_tolerance=1, y_tolerance=3) or "")
    return "\n".join(chunks)


def is_illegitimate_outcome_pdf(pdf_path: Path) -> tuple[bool, str]:
    text = _normalize(_first_pages_text(pdf_path, max_pages=3))
    if not text:
        return False, "primeiras_paginas_sem_texto"

    has_outcome = any(term in text for term in OUTCOME_TERMS)
    has_opening = any(term in text for term in OPENING_TERMS)
    if has_outcome and not has_opening:
        terms = [term for term in OUTCOME_TERMS if term in text]
        return True, ",".join(terms[:4])
    return False, "parece_edital_ou_indefinido"


def _delete_edital(db, edital: db_models.Edital, reason: str, dry_run: bool) -> int:
    total_cargos = len(edital.cargos)
    logger.info(
        "DELETE edital_id=%s orgao=%r cargos=%d motivo=%s",
        edital.id,
        edital.orgao,
        total_cargos,
        reason,
    )
    db.delete(edital)
    if dry_run:
        db.rollback()
    else:
        db.commit()
    return 1


def _find_anchor_pages(pdf, cargo: db_models.Cargo) -> list[int]:
    probes = []
    if cargo.anchor_text:
        normalized_anchor = _normalize(cargo.anchor_text)
        probes.extend([normalized_anchor[:500], normalized_anchor[:250]])
    probes.append(_normalize(cargo.titulo))
    probes = [probe for probe in probes if len(probe) >= 6]

    pages: list[int] = []
    for index, page in enumerate(pdf.pages):
        page_text = _normalize(page.extract_text(x_tolerance=1, y_tolerance=3) or "")
        compact_page = _compact(page_text)
        for probe in probes:
            if probe and (probe in page_text or _compact(probe) in compact_page):
                pages.append(index)
                break
        if len(pages) >= 3:
            break

    if pages:
        expanded = set()
        for page_index in pages:
            for near in range(max(0, page_index - 2), min(len(pdf.pages), page_index + 3)):
                expanded.add(near)
        return sorted(expanded)
    return list(range(min(len(pdf.pages), 12)))


def _rows_to_dataframe(rows: list[list[object]]) -> Optional["pd.DataFrame"]:
    clean_rows: list[list[str]] = []
    for row in rows or []:
        cells = [re.sub(r"\s+", " ", str(cell or "")).strip() for cell in row]
        if any(cells):
            clean_rows.append(cells)
    if len(clean_rows) < 2:
        return None

    width = max(len(row) for row in clean_rows)
    normalized_rows = [row + [""] * (width - len(row)) for row in clean_rows]
    header_index = 0
    for index, row in enumerate(normalized_rows[:4]):
        score = sum(1 for cell in row if _normalize(cell) in {"cargo", "emprego", "funcao", "função", "vagas", "salario", "salário", "requisitos"})
        if score:
            header_index = index
            break

    headers = normalized_rows[header_index]
    if len(set(headers)) != len(headers) or not any(headers):
        headers = [cell if cell else f"col_{idx + 1}" for idx, cell in enumerate(headers)]
    deduped: list[str] = []
    counts: dict[str, int] = {}
    for idx, header in enumerate(headers):
        name = header or f"col_{idx + 1}"
        counts[name] = counts.get(name, 0) + 1
        deduped.append(name if counts[name] == 1 else f"{name}_{counts[name]}")

    data = normalized_rows[header_index + 1 :]
    if not data:
        return None
    df = pd.DataFrame(data, columns=deduped)
    df = df.replace("", pd.NA).dropna(how="all")
    df = df.dropna(axis=1, how="all")
    return df if not df.empty else None


def _slice_dataframe(df: "pd.DataFrame") -> list["pd.DataFrame"]:
    if len(df.columns) <= 10:
        return [df]

    slices = []
    columns = list(df.columns)
    for start in range(0, len(columns), 8):
        selected = columns[start : start + 10]
        slices.append(df[selected])
    return slices


def extract_table_candidates(pdf_path: Path, cargo: db_models.Cargo) -> list[TableCandidate]:
    candidates: list[TableCandidate] = []
    with pdfplumber.open(str(pdf_path)) as pdf:
        page_indexes = _find_anchor_pages(pdf, cargo)
        for page_index in page_indexes:
            page = pdf.pages[page_index]
            table_settings = {
                "vertical_strategy": "lines",
                "horizontal_strategy": "lines",
                "intersection_tolerance": 5,
                "snap_tolerance": 3,
                "join_tolerance": 3,
            }
            tables = page.extract_tables(table_settings=table_settings) or []
            if not tables:
                tables = page.extract_tables() or []
            for table_index, rows in enumerate(tables):
                df = _rows_to_dataframe(rows)
                if df is None:
                    continue
                for sliced in _slice_dataframe(df):
                    candidates.append(
                        TableCandidate(
                            page_number=page_index + 1,
                            table_index=table_index,
                            dataframe=sliced,
                        )
                    )
    return candidates


def _dataframe_preview(df: "pd.DataFrame", max_rows: int = 6) -> str:
    preview = df.head(max_rows).fillna("").astype(str)
    return preview.to_markdown(index=False)


def _heuristic_mapping(df: "pd.DataFrame") -> Optional[ColumnMapping]:
    mapping = ColumnMapping(confidence=0.0, reason="heuristica_insuficiente")

    terms = {
        "cargo": (
            "cargo", "emprego", "funcao", "função", "especialidade", "ocupação",
            "classe", "perfil", "carreira",
        ),
        "vagas": (
            "vaga", "quantidade", "ampla", "ac", "pcd", "negros", "cotas",
            "total", "cr", "v.ac", "v.pcd",
        ),
        "salario": (
            "salario", "salário", "vencimento", "remuneracao", "remuneração",
            "subsidio", "subsídio", "inicial", "valor", "bruto",
        ),
        "escolaridade": (
            "escolaridade", "requisito", "habilitacao", "habilitação", "nivel",
            "nível", "formação", "exigência", "graduação",
        ),
    }
    normalized_terms = {
        field: {(_normalize(term), _compact(term)) for term in field_terms}
        for field, field_terms in terms.items()
    }

    def matches(column_name: str, field: str) -> bool:
        normalized_name = _normalize(column_name)
        compact_name = _compact(column_name)
        tokens = set(re.findall(r"[a-z0-9]+", normalized_name))
        for normalized_term, compact_term in normalized_terms[field]:
            if normalized_term in normalized_name or compact_term in compact_name:
                return True
            if normalized_term in tokens or compact_term in tokens:
                return True
        return False

    for column in df.columns:
        column_name = str(column)
        if not mapping.cargo and matches(column_name, "cargo"):
            mapping.cargo = str(column)
        elif not mapping.vagas and matches(column_name, "vagas"):
            mapping.vagas = str(column)
        elif not mapping.salario and matches(column_name, "salario"):
            mapping.salario = str(column)
        elif not mapping.escolaridade and matches(column_name, "escolaridade"):
            mapping.escolaridade = str(column)

    found_count = sum(1 for v in [mapping.cargo, mapping.vagas, mapping.salario, mapping.escolaridade] if v)

    if mapping.cargo and found_count >= 3:
        mapping.confidence = 0.98
        mapping.reason = "cabecalho_deterministico_avancado"
        return mapping

    return None


async def audit_dataframe_with_llm(df: "pd.DataFrame") -> ColumnMapping:
    heuristic = _heuristic_mapping(df)
    if heuristic:
        return heuristic

    prompt = f"""
Sua tarefa: mapear nomes de colunas de uma tabela para campos fixos.
Responda APENAS JSON, sem markdown.

Campos:
- cargo: nome do cargo.
- vagas: total ou ampla concorrencia.
- salario: vencimento ou remuneracao.
- escolaridade: nivel ou requisito.

Regras:
1. Use APENAS nomes de colunas presentes na lista abaixo.
2. Use null se nao encontrar.
3. Se a confiança for menor que 95% para os 4 campos, use confidence: 0.0.

COLUNAS DISPONIVEIS:
{list(map(str, df.columns))}

AMOSTRA DA TABELA:
{_dataframe_preview(df, max_rows=5)}

RESPOSTA JSON ESPERADA:
{{
  "cargo": "coluna_exata",
  "vagas": "coluna_exata",
  "salario": "coluna_exata",
  "escolaridade": "coluna_exata",
  "confidence": 0.98,
  "reason": "justificativa",
  "tags": []
}}
"""
    for provider in _build_chain():
        try:
            return await provider.generate_json(prompt=prompt, schema=ColumnMapping)
        except Exception as exc:
            logger.warning("%s falhou no mapeamento da tabela: %s", provider.__class__.__name__, exc)

    return ColumnMapping(confidence=0.0, reason="sem_provider_ia_ou_baixa_confianca", tags=["#SCAN_SUJO"])


def _find_column(df: "pd.DataFrame", requested: Optional[str]) -> Optional[str]:
    if not requested:
        return None
    if requested in df.columns:
        return requested
    normalized = _normalize(requested)
    for column in df.columns:
        if _normalize(str(column)) == normalized:
            return str(column)
    return None


def _row_matches_cargo(row, column: str, cargo_title: str) -> bool:
    value = str(row.get(column, "") or "")
    if not value.strip():
        return False
    row_key = _compact(value)
    cargo_key = _compact(cargo_title)
    return cargo_key in row_key or row_key in cargo_key


def _parse_salary(value) -> Optional[float]:
    text = str(value or "").strip()
    if not text:
        return None
    match = re.search(r"(\d{1,3}(?:\.\d{3})*,\d{2}|\d+(?:,\d{2})?)", text)
    if not match:
        return None
    number = match.group(1).replace(".", "").replace(",", ".")
    try:
        return float(number)
    except ValueError:
        return None


def _parse_vacancies(value) -> Optional[str]:
    text = re.sub(r"\s+", " ", str(value or "")).strip()
    if not text:
        return None
    return text[:50]


def _apply_row_rescue(db, cargo: db_models.Cargo, row, mapping: ColumnMapping, dry_run: bool) -> RescueResult:
    changed = False
    salary_col = _find_column(row.to_frame().T, mapping.salario)
    education_col = _find_column(row.to_frame().T, mapping.escolaridade)
    vacancies_col = _find_column(row.to_frame().T, mapping.vagas)

    salary = _parse_salary(row.get(salary_col)) if salary_col else None
    if salary and (cargo.salario is None or cargo.salario <= 0):
        cargo.salario = salary
        changed = True

    education = str(row.get(education_col, "") or "").strip() if education_col else ""
    if _has_value(education) and not _has_value(cargo.escolaridade):
        cargo.escolaridade = education[:100]
        changed = True

    vacancies = _parse_vacancies(row.get(vacancies_col)) if vacancies_col else None
    if vacancies and not any(_has_value(getattr(cargo, field, None)) for field in VACANCY_FIELDS):
        cargo.vagas_total = vacancies
        changed = True

    if not changed:
        return RescueResult(False, cargo.status, "linha_sem_dados_novos")

    cargo.status = "vitaminado"
    if dry_run:
        db.rollback()
    else:
        db.commit()
    return RescueResult(True, "vitaminado", "tabela_validada")


async def rescue_cargo_from_tables(db, cargo: db_models.Cargo, pdf_path: Path, dry_run: bool) -> RescueResult:
    candidates = extract_table_candidates(pdf_path, cargo)
    if not candidates:
        cargo.status = SCAN_STATUS
        if dry_run:
            db.rollback()
        else:
            db.commit()
        return RescueResult(False, SCAN_STATUS, "sem_tabelas_proximas")

    for candidate in candidates:
        mapping = await audit_dataframe_with_llm(candidate.dataframe)
        logger.info(
            "Tabela cargo_id=%s pagina=%d tabela=%d confianca=%.2f colunas=%s motivo=%s",
            cargo.id,
            candidate.page_number,
            candidate.table_index,
            mapping.confidence,
            mapping.model_dump(exclude={"reason", "tags"}),
            mapping.reason,
        )
        if mapping.confidence < 0.95:
            continue

        cargo_col = _find_column(candidate.dataframe, mapping.cargo)
        if not cargo_col:
            continue

        for _, row in candidate.dataframe.fillna("").iterrows():
            if not _row_matches_cargo(row, cargo_col, cargo.titulo):
                continue
            return _apply_row_rescue(db, cargo, row, mapping, dry_run=dry_run)

    cargo.status = DOU_STATUS if "dou" in _normalize(cargo.anchor_text or "") else SCAN_STATUS
    if dry_run:
        db.rollback()
    else:
        db.commit()
    return RescueResult(False, cargo.status, "mapeamento_baixa_confianca_ou_sem_linha")


async def process_edital(edital_id: str, dry_run: bool, no_hash_scan: bool) -> tuple[int, int, int]:
    db = SessionLocal()
    try:
        edital = (
            db.query(db_models.Edital)
            .options(selectinload(db_models.Edital.cargos))
            .filter(db_models.Edital.id == edital_id)
            .first()
        )
        if not edital:
            return 0, 0, 0

        quarantined = [cargo for cargo in edital.cargos if cargo.status == "quarentena"]
        if not quarantined:
            return 0, 0, 0

        pdf_path = resolve_pdf_path(edital, scan_storage=not no_hash_scan)
        if not pdf_path:
            logger.info("Lvl2 edital_id=%s orgao=%r motivo=pdf_nao_localizado", edital.id, edital.orgao)
            for cargo in quarantined:
                cargo.status = SCAN_STATUS
            if dry_run:
                db.rollback()
            else:
                db.commit()
            return 0, 0, len(quarantined)

        illegitimate, reason = is_illegitimate_outcome_pdf(pdf_path)
        if illegitimate:
            return _delete_edital(db, edital, reason, dry_run=dry_run), 0, 0

        rescued = 0
        lvl2 = 0
        for cargo in quarantined:
            logger.info("Arquitetando cargo_id=%s titulo=%r pdf=%s", cargo.id, cargo.titulo, pdf_path)
            result = await rescue_cargo_from_tables(db, cargo, pdf_path, dry_run=dry_run)
            if result.rescued:
                rescued += 1
            else:
                lvl2 += 1
            logger.info(
                "Resultado cargo_id=%s status=%s resgatado=%s motivo=%s",
                cargo.id,
                result.status,
                result.rescued,
                result.reason,
            )
        return 0, rescued, lvl2
    except Exception as exc:
        db.rollback()
        logger.exception("Erro no edital_id=%s: %s", edital_id, exc)
        return 0, 0, 1
    finally:
        db.close()


async def main(limit: Optional[int], dry_run: bool, no_hash_scan: bool) -> None:
    if missing_dependency:
        raise SystemExit(
            "Dependencias ausentes. Instale com: pip install pdfplumber pandas "
            f"(erro: {missing_dependency})"
        )

    db = SessionLocal()
    try:
        query = (
            db.query(db_models.Edital.id, db_models.Edital.created_at)
            .join(db_models.Cargo)
            .filter(db_models.Cargo.status == "quarentena")
            .distinct()
            .order_by(db_models.Edital.created_at.asc())
        )
        if limit:
            query = query.limit(limit)
        edital_ids = [str(row[0]) for row in query.all()]
    except SQLAlchemyError as exc:
        logger.error("Banco indisponivel ou schema ausente: %s", exc)
        raise SystemExit(f"Banco indisponivel ou schema ausente: {exc}") from exc
    finally:
        db.close()

    logger.info(
        "O Arquiteto iniciado: %d edital(is) com quarentena.%s",
        len(edital_ids),
        " [DRY RUN]" if dry_run else "",
    )

    deleted = 0
    rescued = 0
    lvl2 = 0
    for index, edital_id in enumerate(edital_ids, start=1):
        logger.info("[%d/%d] Auditando edital_id=%s", index, len(edital_ids), edital_id)
        d_count, r_count, l_count = await process_edital(edital_id, dry_run=dry_run, no_hash_scan=no_hash_scan)
        deleted += d_count
        rescued += r_count
        lvl2 += l_count

    message = f"{deleted} Editais Deletados (Lixo), {rescued} Cargos Resgatados (Tabelas), {lvl2} Triados para Lvl 2"
    logger.info(message)
    print(message)


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description="O Arquiteto - auditor final de tabelas em quarentena.")
    parser.add_argument("--limit", type=int, default=None, help="Limite de editais com cargos em quarentena.")
    parser.add_argument("--dry-run", action="store_true", help="Executa sem gravar alteracoes no banco.")
    parser.add_argument(
        "--no-hash-scan",
        action="store_true",
        help="Nao varre storage_k/sample_editais calculando hash dos PDFs.",
    )
    args = parser.parse_args()

    asyncio.run(main(limit=args.limit, dry_run=args.dry_run, no_hash_scan=args.no_hash_scan))
