import json
import logging
import re
import io
import math
import pandas as pd
from collections import Counter
from dataclasses import dataclass, field
from pathlib import Path
from typing import Dict, Tuple, Any

logger = logging.getLogger(__name__)

STORAGE_BASE = Path("storage/processed")

@dataclass
class StorageResult:
    """Resultado da operação de persistência do SubtractiveAgent."""
    content_hash: str
    main_md: str      # O padrão estrutural (com markers)
    data_md: str      # Focado em tabelas e dados brutos
    clean_md: str     # Apenas texto de conteúdo programático (sem ruído/tabelas)
    tables: Dict[str, str] = field(default_factory=dict)
    patterns: Dict[str, Any] = field(default_factory=dict)

# Matches one or more consecutive lines that start (after optional whitespace) with |
_TABLE_RE = re.compile(r'(?m)(?:^[ \t]*\|[^\n]*(?:\n|$))+')

# Matches Brazilian monetary values: R$ 1.234,56 or R$1234
_MONEY_RE = re.compile(r'R\$\s*[\d.,]+')

# Matches dates: DD/MM/YYYY or DD/MM/YY
_DATE_RE = re.compile(r'\b\d{2}/\d{2}/(?:\d{4}|\d{2})\b')


class SubtractiveAgent:
    """Gera a Trindade de Markdowns para otimizar o contexto dos agentes."""

    def strip_tables(self, md: str) -> Tuple[str, Dict[str, str]]:
        """Remove markdown table blocks and replace with markers.

        Returns:
            (stripped_md, fragments) where fragments maps marker keys to original content.
        """
        fragments: Dict[str, str] = {}
        counter = 0

        def _replacer(match: re.Match) -> str:
            nonlocal counter
            key = f"FRAGMENT_TABLE_{counter}"
            fragments[key] = match.group(0)
            counter += 1
            return f"[[{key}]]"

        stripped = _TABLE_RE.sub(_replacer, md)
        logger.debug(f"strip_tables: removed {len(fragments)} table(s).")
        return stripped, fragments

    def strip_patterns(self, md: str) -> Tuple[str, Dict[str, str]]:
        """Remove monetary values and dates, replacing with markers.

        Returns:
            (stripped_md, fragments)
        """
        fragments: Dict[str, str] = {}
        money_counter = 0
        date_counter = 0

        def _money_replacer(match: re.Match) -> str:
            nonlocal money_counter
            key = f"FRAGMENT_MONEY_{money_counter}"
            fragments[key] = match.group(0)
            money_counter += 1
            return f"[[{key}]]"

        def _date_replacer(match: re.Match) -> str:
            nonlocal date_counter
            key = f"FRAGMENT_DATE_{date_counter}"
            fragments[key] = match.group(0)
            date_counter += 1
            return f"[[{key}]]"

        stripped = _MONEY_RE.sub(_money_replacer, md)
        stripped = _DATE_RE.sub(_date_replacer, stripped)
        logger.debug(f"strip_patterns: removed {money_counter} monetary value(s), {date_counter} date(s).")
        return stripped, fragments

    def process(self, md: str) -> StorageResult:
        """Gera main.md, data.md e clean.md a partir do markdown bruto."""
        # 1. Limpeza de ruído base
        before_noise = len(md)
        base_md = self._suppress_noise(md)
        noise_removed = before_noise - len(base_md)
        logger.info(f"suppress_noise: {before_noise} → {len(base_md)} chars (−{noise_removed} removed)")

        # 2. Gerar DATA.MD (Foco em tabelas e extração estrutural)
        # Identificamos todas as tabelas e as mantemos explícitas
        tables_found = _TABLE_RE.findall(base_md)
        data_md = "\n\n".join([self._format_table_md(t) for t in tables_found])
        
        # 3. Gerar MAIN.MD (Estrutural com marcadores para ancoragem)
        stripped_main, table_fragments = self.strip_tables(base_md)
        stripped_main, pattern_fragments = self.strip_patterns(stripped_main)
        stripped_main = re.sub(r'\n{3,}', '\n\n', stripped_main).strip()
        
        # 4. Gerar CLEAN.MD (Apenas seções programáticas, sem ruído)
        programmatic = self._extract_programmatic_sections(base_md) or base_md
        clean_md = self._strip_tables_preserving_programmatic(programmatic)
        clean_md = _MONEY_RE.sub("", clean_md)
        clean_md = _DATE_RE.sub("", clean_md)
        clean_md = re.sub(r'\n{3,}', '\n\n', clean_md).strip()

        # Extração de metadados extras
        all_fragments = {**table_fragments, **pattern_fragments}
        metadata_extras = self._extract_metadata(md)
        all_fragments.update(metadata_extras)

        return StorageResult(
            content_hash="", # Será preenchido pelo caller
            main_md=stripped_main,
            data_md=data_md,
            clean_md=clean_md,
            tables=table_fragments,
            patterns=pattern_fragments
        )

    # Padrões que marcam o início de uma seção de conteúdo programático
    _PROG_PATTERNS = re.compile(
        r"(?:CONTEÚDO PROGRAMÁTICO"
        r"|DOS CONTEÚDOS PROGRAMÁTICOS"
        r"|PROGRAMA DE PROVAS"
        r"|PROVAS OBJETIVAS[\s\S]{0,60}CONHECIMENTOS"
        r"|ANEXO\s+[IVX\d]+[\s\S]{0,60}CONTEÚDO)",
        re.IGNORECASE,
    )

    def _extract_programmatic_sections(self, text: str) -> str:
        """Retorna o texto a partir da linha que contém a primeira seção de conteúdo programático."""
        m = self._PROG_PATTERNS.search(text)
        if not m:
            return ""
        line_start = text.rfind('\n', 0, m.start())
        start = line_start + 1 if line_start != -1 else 0
        return text[start:]

    def _extract_metadata(self, md_content: str) -> Dict[str, Any]:
        """Extrai URLs e e-mails do markdown original."""
        # Regex para URLs (http/https)
        url_pattern = r'https?://(?:[-\w.]|(?:%[\da-fA-F]{2}))+[/\w\.-]*(?:\?\S+)?'
        # Regex para e-mails
        email_pattern = r'[a-zA-Z0-9._%+-]+@[a-zA-Z0-9.-]+\.[a-zA-Z]{2,}'

        urls = re.findall(url_pattern, md_content)
        emails = re.findall(email_pattern, md_content)

        return {
            "links": sorted(list(set(urls))),
            "contact_emails": sorted(list(set(emails)))
        }

    def _suppress_noise(self, md_content: str) -> str:
        """Remove cabeçalhos e rodapés repetitivos (ruído) do markdown."""
        if re.search(r'\n-{3,}\n', md_content):
            page_sep = re.compile(r'\n-{3,}\n')
        else:
            page_sep = re.compile(r'\n{2,}')

        raw_pages = [p.strip() for p in page_sep.split(md_content) if p.strip()]
        n_pages = len(raw_pages)

        def _clean_page(page: str) -> str:
            page = re.sub(r'(?m)^[ \t]*[-_*]{3,}[ \t]*$', '', page)
            page = re.sub(r'(?m)^[ \t]*-?\s*\d+\s*-?[ \t]*$', '', page)
            return page

        pages = [_clean_page(p) for p in raw_pages]

        if n_pages < 3:
            return "\n\n".join(pages)

        def _normalize(line: str) -> str:
            return re.sub(r'\d+$', '#', line.strip())

        norm_counts: Counter = Counter()
        for page in pages:
            seen_norms: set = set()
            for raw in page.splitlines():
                stripped = raw.strip()
                if len(stripped) < 5:
                    continue
                norm = _normalize(stripped)
                if norm not in seen_norms:
                    norm_counts[norm] += 1
                    seen_norms.add(norm)

        threshold = max(3, math.ceil(n_pages * 0.30))
        noisy_norms = {norm for norm, count in norm_counts.items() if count >= threshold}

        clean_pages = []
        for page in pages:
            clean_lines = [
                l for l in page.splitlines()
                if _normalize(l) not in noisy_norms
            ]
            joined = "\n".join(clean_lines)
            if joined.strip():
                clean_pages.append(joined)

        return "\n\n".join(clean_pages)

    def _strip_tables_preserving_programmatic(self, md: str) -> str:
        """Strip tables from md, keeping any table whose cell contains a programmatic marker."""
        def _maybe_strip(match: re.Match) -> str:
            if self._PROG_PATTERNS.search(match.group(0)):
                return match.group(0)
            return ""
        return _TABLE_RE.sub(_maybe_strip, md)

    def _format_table_md(self, raw_table_md: str) -> str:
        """Reformata uma tabela markdown bruta usando pandas."""
        try:
            lines = [l.strip() for l in raw_table_md.strip().splitlines() if l.strip()]
            if len(lines) < 2:
                return raw_table_md

            content_lines = []
            for i, line in enumerate(lines):
                if i == 1 and all(c in '|- : \t' for c in line) and '-' in line:
                    continue
                content_lines.append(line)

            df = pd.read_csv(
                io.StringIO('\n'.join(content_lines)),
                sep='|',
                skipinitialspace=True
            )
            df = df.loc[:, ~df.columns.str.contains('^Unnamed')]
            df = df.apply(lambda x: x.str.strip() if x.dtype == "object" else x)
            df.columns = [c.strip() for c in df.columns]

            return df.to_markdown(index=False)
        except Exception as e:
            return raw_table_md

    def persist(self, result: StorageResult, storage_base: Path = None) -> str:
        """Persiste a Trindade em storage_base/{content_hash}/."""
        if storage_base is None:
            storage_base = STORAGE_BASE
        storage_path = Path(storage_base).resolve() / result.content_hash
        tables_dir = storage_path / "tables"

        storage_path.mkdir(parents=True, exist_ok=True)
        tables_dir.mkdir(exist_ok=True)

        # A Trindade
        (storage_path / "main.md").write_text(result.main_md, encoding="utf-8")
        (storage_path / "data.md").write_text(result.data_md, encoding="utf-8")
        (storage_path / "clean.md").write_text(result.clean_md, encoding="utf-8")

        # Salvar tabelas individuais
        table_keys = sorted(result.tables.keys())
        for i, key in enumerate(table_keys):
            table_path = tables_dir / f"tabela_{i}.md"
            formatted_table = self._format_table_md(result.tables[key])
            table_path.write_text(formatted_table, encoding="utf-8")

        # Salvar metadados
        metadata = {
            "content_hash": result.content_hash,
            "patterns": result.patterns,
            "table_count": len(result.tables),
            "trinity": True
        }
        (storage_path / "metadata.json").write_text(
            json.dumps(metadata, ensure_ascii=False, indent=2), 
            encoding="utf-8"
        )

        logger.info(f"persist: {result.content_hash} → TRINITY (main, data, clean)")
        return str(storage_path)
