"""
CargoMapper — Camada 1 do AnchorEngine.

Extração determinística de cargos via Pandas + regex, sem LLM.

Fluxo:
  1. Escaneia tables/*.md procurando colunas de cargo.
  2. Se nenhum seed encontrado → escaneia início do main.md
     (captura "NOME DE RELACIONAMENTO: X" e prose genérica).
  3. Deduplicação dupla: chave exata + remoção de prefixos
     (ex: "Analista Judiciário – Área Apoio" absorvido por versão completa).
"""
from __future__ import annotations

import logging
import re
import unicodedata
from dataclasses import dataclass
from pathlib import Path
from typing import List, Optional

logger = logging.getLogger(__name__)

# ── Column keyword matchers ─────────────────────────────────────────────────

_CARGO_COL_RE = re.compile(
    r"(cargo/fun[çc][aã]o|cargo/perfil|cargo/ocupação|cargo|fun[çc][aã]o|especialidade|ocupa[çc][aã]o|perfil|posto|denomina[çc][aã]o)",
    re.IGNORECASE,
)
_CODE_COL_RE = re.compile(r"\b(c[oó]d(?:igo)?\.?|item)\b", re.IGNORECASE)
_VAGAS_TOTAL_COL_RE = re.compile(r"\b(total|total\s+de\s+vagas|vagas\s+totais)\b", re.IGNORECASE)

# Geographic distribution tables — skip their prose fallback when no cargo column found
_GEO_COL_RE = re.compile(
    r"\b(uf|macro|micro|munic[ií]pio|cidade|regi[aã]o|localidade)\b",
    re.IGNORECASE,
)

# Section-header tables: "NÍVEL SUPERIOR (exceto área X)" are program-content labels, not cargos
_SECTION_HEADER_RE = re.compile(
    r"\bNÍVEL\s+(SUPERIOR|MÉDIO|FUNDAMENTAL)\b",
    re.IGNORECASE,
)

# Prose: cargo-name starters (Brazilian civil-service vocabulary)
_CARGO_PROSE_RE = re.compile(
    r"(?:^|(?<=\|))\s*((?:Analista|T[eé]cnico|Agente|Perito|Auditor|Escrivão|Delegado"
    r"|Inspetor|Assistente|Auxiliar|Operador|Oficial|M[eé]dico|Enfermeiro"
    r"|Contador|Engenheiro|Procurador|Defensor|Promotor|Juiz|Psic[oó]logo"
    r"|Farmac[eê]utico|Odont[oó]logo|Nutricionista|Motorista|Vigilante"
    r"|Administrador|Economista|Advogado|Gestor|Coordenador|Escritur[aá]rio)"
    r"[^\n|]{5,180})",
    re.IGNORECASE | re.MULTILINE,
)

# main.md fallback: "NOME(S) DE RELACIONAMENTO: X" (BB-style cargo aliases)
# Stop at newline, sentence boundaries, AND closing paren — avoids bleeding into next sentence
_RELACIONAMENTO_RE = re.compile(
    r"NOME[S]?\s+DE\s+RELACIONAMENTO:?\s+([A-ZÁÉÍÓÚÂÊÔÀÃÕA-Za-záéíóúâêôàãõ][^\n.:;|),]{3,60})",
    re.IGNORECASE,
)

# Minimum set of valid words for a cargo start
_CARGO_START_RE = re.compile(
    r"^(Analista|T[eé]cnico|Agente|Perito|Auditor|Escrivão|Delegado|Inspetor"
    r"|Assistente|Auxiliar|Operador|Oficial|M[eé]dico|Enfermeiro|Contador"
    r"|Engenheiro|Procurador|Defensor|Promotor|Juiz(?!\s+de\s+fora)|Psic[oó]logo|Farmac[eê]utico"
    r"|Odont[oó]logo|Nutricionista|Motorista|Vigilante|Administrador|Economista"
    r"|Advogado|Gestor|Coordenador|Escritur[aá]rio)",
    re.IGNORECASE,
)

_MIN_LEN = 8
_MAX_LEN = 200
_MIN_WORDS_TABLE = 3     # for table-based extraction (stricter)
_MIN_WORDS_PROSE = 2     # for prose/main.md scan (more permissive — "Agente Comercial" = 2w)


@dataclass
class CargoSeed:
    titulo: str
    codigo: Optional[str] = None
    vagas_totais_string: Optional[str] = None
    source_file: Optional[str] = None


class CargoMapper:
    """Extrai CargoSeed de tables/*.md (e main.md como fallback) sem LLM."""

    def map(self, content_hash: str) -> List[CargoSeed]:
        storage = self._resolve_storage(content_hash)
        if storage is None:
            logger.error("CargoMapper: storage not found for %s", content_hash[:12])
            return []

        # Step 1: scan tables (tables/ directory remains for individual debug, but we prefer data.md for unified scan)
        seeds = self._scan_data_md(storage, content_hash)
        
        # Se data.md falhou ou não existe, fallback para o diretório de tables
        if not seeds:
            seeds = self._scan_tables(storage, content_hash)

        # Step 2: if tables yielded nothing, scan main.md (BB-style: cargos in prose)
        if not seeds:
            logger.info(
                "CargoMapper [%s]: tables empty → scanning main.md",
                content_hash[:12],
            )
            seeds = self._scan_main_md(storage)

        result = self._deduplicate(seeds)
        logger.info(
            "CargoMapper [%s]: %d raw → %d unique seeds",
            content_hash[:12], len(seeds), len(result),
        )
        return result

    def _scan_data_md(self, storage: Path, content_hash: str) -> List[CargoSeed]:
        data_md = storage / "data.md"
        if not data_md.exists():
            return []
        
        try:
            found = self._extract_from_file(data_md)
            if found:
                logger.info("CargoMapper [%s]: %d seeds extraídos do DATA.MD", content_hash[:12], len(found))
                return found
        except Exception as exc:
            logger.debug("CargoMapper DATA.MD error: %s", exc)
        return []

    # ── Step 1: tables ─────────────────────────────────────────────────────

    def _scan_tables(self, storage: Path, content_hash: str) -> List[CargoSeed]:
        tables_dir = storage / "tables"
        if not tables_dir.exists():
            return []

        raw: List[CargoSeed] = []
        for tf in sorted(tables_dir.glob("*.md")):
            try:
                found = self._extract_from_file(tf)
                if found:
                    raw.extend(found)
                    logger.info(
                        "CargoMapper [%s] %s → %d seeds",
                        content_hash[:12], tf.name, len(found),
                    )
            except Exception as exc:
                logger.debug("CargoMapper skip %s: %s", tf.name, exc)

        return raw

    def _extract_from_file(self, path: Path) -> List[CargoSeed]:
        text = path.read_text(encoding="utf-8")
        if not text.strip():
            return []

        rows = self._parse_md_rows(text)
        if rows and len(rows) >= 2:
            result = self._extract_from_rows(rows, path.name)
            if result:
                return result

        return self._extract_from_prose(text, path.name, min_words=_MIN_WORDS_TABLE)

    def _parse_md_rows(self, text: str) -> List[List[str]]:
        pipe_lines = [line for line in text.splitlines() if "|" in line]
        if len(pipe_lines) < 2:
            return []
        data = [l for l in pipe_lines if not re.match(r"^\s*\|?[-:\s|]+\|?\s*$", l)]
        return [[c.strip() for c in l.strip().strip("|").split("|")] for l in data]

    def _extract_from_rows(self, rows: List[List[str]], filename: str) -> List[CargoSeed]:
        if len(rows) < 2:
            return []

        header = rows[0]
        data_rows = rows[1:]

        # Skip section-header tables (NÍVEL SUPERIOR/MÉDIO content-program labels)
        if len(header) == 1 and _SECTION_HEADER_RE.search(header[0]):
            return []

        cargo_idxs = [i for i, h in enumerate(header) if _CARGO_COL_RE.search(h)]
        if not cargo_idxs:
            return []

        code_idxs = [i for i, h in enumerate(header) if _CODE_COL_RE.search(h)]
        vagas_idxs = [i for i, h in enumerate(header) if _VAGAS_TOTAL_COL_RE.search(h)]

        seeds: List[CargoSeed] = []
        for row in data_rows:
            ncols = len(header)
            padded = row + [""] * (ncols - len(row)) if len(row) < ncols else row

            parts = []
            for idx in cargo_idxs:
                if idx < len(padded):
                    val = padded[idx].strip()
                    if val and val.lower() not in ("nan", "none", ""):
                        parts.append(val)
            titulo = " – ".join(parts) if len(parts) > 1 else (parts[0] if parts else "")
            titulo = self._clean(titulo)
            if not titulo or not (_MIN_LEN <= len(titulo) <= _MAX_LEN):
                continue
            if not _CARGO_START_RE.match(titulo):
                continue
            if len(titulo.split()) < _MIN_WORDS_TABLE:
                continue
            if _SECTION_HEADER_RE.search(titulo):
                continue

            codigo: Optional[str] = None
            for idx in code_idxs:
                if idx < len(padded):
                    val = padded[idx].strip()
                    if val and val.lower() not in ("nan", "none", ""):
                        codigo = val
                        break

            vagas: Optional[str] = None
            for idx in vagas_idxs:
                if idx < len(padded):
                    val = padded[idx].strip()
                    if val and val.lower() not in ("nan", "none", ""):
                        vagas = val
                        break

            seeds.append(CargoSeed(titulo=titulo, codigo=codigo, vagas_totais_string=vagas, source_file=filename))

        return seeds

    def _extract_from_prose(self, text: str, filename: str, min_words: int) -> List[CargoSeed]:
        # Skip geographic tables for prose scan (no cargo column headers)
        first_pipe_line = next((l for l in text.splitlines() if "|" in l), "")
        if _GEO_COL_RE.search(first_pipe_line) and not _CARGO_COL_RE.search(first_pipe_line):
            return []

        seeds: List[CargoSeed] = []
        for m in _CARGO_PROSE_RE.finditer(text):
            titulo = self._clean(m.group(1))
            if not (_MIN_LEN <= len(titulo) <= _MAX_LEN):
                continue
            if not _CARGO_START_RE.match(titulo):
                continue
            if len(titulo.split()) < min_words:
                continue
            if _SECTION_HEADER_RE.search(titulo):
                continue
            seeds.append(CargoSeed(titulo=titulo, source_file=filename))
        return seeds

    # ── Step 2: main.md fallback ────────────────────────────────────────────

    def _scan_main_md(self, storage: Path) -> List[CargoSeed]:
        main_md = storage / "main.md"
        if not main_md.exists():
            return []

        text = main_md.read_text(encoding="utf-8")[:6_000]
        seeds: List[CargoSeed] = []

        # Priority: extract from "NOME DE RELACIONAMENTO: X" (BB-style)
        for m in _RELACIONAMENTO_RE.finditer(text):
            raw = m.group(1).strip()
            # May be "Agente de Tecnologia e Agente Comercial" — split by connectors
            parts = re.split(r"\s+e\s+|,\s*", raw)
            for part in parts:
                titulo = self._clean(part)
                if (
                    len(titulo) >= _MIN_LEN
                    and len(titulo.split()) >= _MIN_WORDS_PROSE
                    and _CARGO_START_RE.match(titulo)
                ):
                    seeds.append(CargoSeed(titulo=titulo, source_file="main.md"))

        # General prose scan (lowered word-count threshold for fallback context)
        seeds.extend(self._extract_from_prose(text, "main.md", min_words=_MIN_WORDS_PROSE))

        return seeds

    # ── Deduplication ────────────────────────────────────────────────────────

    def _deduplicate(self, seeds: List[CargoSeed]) -> List[CargoSeed]:
        # Phase 1: exact normalized-key dedup
        seen: dict[str, CargoSeed] = {}
        for s in seeds:
            key = self._normalize(s.titulo)
            if key not in seen:
                seen[key] = s
            else:
                existing = seen[key]
                if not existing.codigo and s.codigo:
                    existing.codigo = s.codigo
                if not existing.vagas_totais_string and s.vagas_totais_string:
                    existing.vagas_totais_string = s.vagas_totais_string

        # Phase 2: prefix/substring dedup — remove shorter keys that are proper
        # prefixes of longer ones (e.g., "Analista Judiciário – Área Apoio"
        # absorbed by "Analista Judiciário – Área Apoio – Especialidade Engenharia")
        sorted_keys = sorted(seen.keys(), key=len)
        to_remove: set[str] = set()

        for i, short in enumerate(sorted_keys):
            if short in to_remove:
                continue
            for long in sorted_keys[i + 1:]:
                if long.startswith(short + " "):
                    to_remove.add(short)
                    # Promote short's metadata to the surviving long key
                    s_short = seen[short]
                    s_long = seen[long]
                    if not s_long.codigo and s_short.codigo:
                        s_long.codigo = s_short.codigo
                    if not s_long.vagas_totais_string and s_short.vagas_totais_string:
                        s_long.vagas_totais_string = s_short.vagas_totais_string
                    break

        return [v for k, v in seen.items() if k not in to_remove]

    # ── Utilities ────────────────────────────────────────────────────────────

    @staticmethod
    def _clean(s: str) -> str:
        s = s.lstrip("|").strip()
        s = re.sub(r"[*_`]", "", s)
        s = re.sub(r"\s+", " ", s)
        s = re.sub(r"[\s\-–/,]+$", "", s).strip()
        return s

    @staticmethod
    def _normalize(title: str) -> str:
        t = unicodedata.normalize("NFD", title.lower())
        t = "".join(c for c in t if unicodedata.category(c) != "Mn")
        # Normalize all separators (dash, em-dash, slash, comma, parens) to space
        t = re.sub(r"[\s\-–/,()\.\|]+", " ", t).strip()
        return t

    @staticmethod
    def _resolve_storage(content_hash: str) -> Optional[Path]:
        for candidate in [
            Path("backend/storage/processed") / content_hash,
            Path("storage/processed") / content_hash,
            Path("/app/storage/processed") / content_hash,
        ]:
            if candidate.exists():
                return candidate
        return None
