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
    stripped_md: str
    tables: Dict[str, str] = field(default_factory=dict)
    patterns: Dict[str, Any] = field(default_factory=dict)

# Matches one or more consecutive lines that start (after optional whitespace) with |
_TABLE_RE = re.compile(r'(?m)(?:^[ \t]*\|[^\n]*(?:\n|$))+')

# Matches Brazilian monetary values: R$ 1.234,56 or R$1234
_MONEY_RE = re.compile(r'R\$\s*[\d.,]+')

# Matches dates: DD/MM/YYYY or DD/MM/YY
_DATE_RE = re.compile(r'\b\d{2}/\d{2}/(?:\d{4}|\d{2})\b')


class SubtractiveAgent:
    """Removes known structures from Markdown, replacing them with [[FRAGMENT_*]] markers."""

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

    def process(self, md: str) -> Tuple[str, Dict[str, str]]:
        """Full subtractive pass: tables first, then monetary values and dates.

        Tables are stripped first so their embedded R$ and dates are captured
        as part of the table fragment, not as loose pattern fragments.

        Returns:
            (markdown_enxuto, all_fragments)
        """
        stripped, table_fragments = self.strip_tables(md)
        stripped, pattern_fragments = self.strip_patterns(stripped)
        all_fragments = {**table_fragments, **pattern_fragments}
        
        # Enriquecer com links e e-mails
        metadata_extras = self._extract_metadata(md)
        all_fragments.update(metadata_extras)

        reduction = len(md) - len(stripped)
        logger.info(
            f"SubtractiveAgent.process: {len(md)} → {len(stripped)} chars "
            f"(−{reduction}, {len(table_fragments)} tables, "
            f"{len(pattern_fragments)} patterns)"
        )
        return stripped, all_fragments

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
        """Remove cabeçalhos e rodapés repetitivos (ruído) do markdown.
        
        Usa frequência de linhas em 'páginas' (separadas por --- ou \n\n).
        """
        # Identificar separador de página (preferir --- se existir)
        page_sep = "\n---\n" if "\n---\n" in md_content else "\n\n"
        pages = [p.strip() for p in md_content.split(page_sep) if p.strip()]
        n_pages = len(pages)
        
        if n_pages < 3:
            return md_content

        # Contar ocorrências de cada linha por página (para evitar contar 10x na mesma pág)
        line_counts = Counter()
        for page in pages:
            unique_lines = set(l.strip() for l in page.splitlines() if len(l.strip()) >= 5)
            for line in unique_lines:
                line_counts[line] += 1

        # Identificar ruído: aparece em >= 30% das páginas E >= 3 vezes
        threshold = max(3, math.ceil(n_pages * 0.30))
        noisy_lines = {line for line, count in line_counts.items() if count >= threshold}

        if noisy_lines:
            logger.info(f"suppress_noise: identificadas {len(noisy_lines)} linhas de ruído.")

        # Reconstruir o texto removendo as linhas ruidosas
        clean_pages = []
        for page in pages:
            clean_lines = [l for l in page.splitlines() if l.strip() not in noisy_lines]
            clean_pages.append("\n".join(clean_lines))

        return page_sep.join(clean_pages)

    def _format_table_md(self, raw_table_md: str) -> str:
        """Reformata uma tabela markdown bruta usando pandas para alinhamento e limpeza.
        
        Inclui fallback para o original em caso de erro de parsing.
        """
        try:
            # Limpeza básica: remover linhas vazias
            lines = [l.strip() for l in raw_table_md.strip().splitlines() if l.strip()]
            if len(lines) < 2:
                return raw_table_md

            # Remover linha de separadores (---) para facilitar o parsing do pandas
            # Geralmente é a segunda linha
            content_lines = []
            for i, line in enumerate(lines):
                if i == 1 and all(c in '|- : \t' for c in line) and '-' in line:
                    continue
                content_lines.append(line)

            # Ler com pandas
            df = pd.read_csv(
                io.StringIO('\n'.join(content_lines)),
                sep='|',
                skipinitialspace=True
            )

            # Remover colunas "Unnamed" que surgem de pipes nas extremidades
            df = df.loc[:, ~df.columns.str.contains('^Unnamed')]
            
            # Limpeza de strings em todas as células
            df = df.apply(lambda x: x.str.strip() if x.dtype == "object" else x)
            
            # Limpeza dos nomes das colunas
            df.columns = [c.strip() for c in df.columns]

            return df.to_markdown(index=False)
        except Exception as e:
            logger.warning(f"Falha ao formatar tabela com pandas ({e}). Usando raw.")
            return raw_table_md

    def persist(self, result: StorageResult, storage_base: Path = None) -> str:
        """Persiste os artefatos em storage_base/{content_hash}/.

        Cria:
            {content_hash}/main.md        — texto limpo
            {content_hash}/tables/        — tabelas individuais
            {content_hash}/metadata.json  — padrões extraídos

        Args:
            result: Objeto StorageResult com os dados processados.
            storage_base: Diretório raiz para armazenamento.

        Returns:
            Caminho absoluto da pasta criada como string.
        """
        if storage_base is None:
            storage_base = STORAGE_BASE
        storage_path = Path(storage_base).resolve() / result.content_hash
        tables_dir = storage_path / "tables"

        storage_path.mkdir(parents=True, exist_ok=True)
        tables_dir.mkdir(exist_ok=True)

        # Suprimir ruído e salvar texto limpo
        clean_md = self._suppress_noise(result.stripped_md)
        (storage_path / "main.md").write_text(clean_md, encoding="utf-8")

        # Salvar tabelas
        table_keys = sorted(result.tables.keys())
        for i, key in enumerate(table_keys):
            table_path = tables_dir / f"tabela_{i}.md"
            formatted_table = self._format_table_md(result.tables[key])
            table_path.write_text(formatted_table, encoding="utf-8")

        # Salvar metadados
        metadata = {
            "content_hash": result.content_hash,
            "patterns": result.patterns,
            "table_count": len(result.tables)
        }
        (storage_path / "metadata.json").write_text(
            json.dumps(metadata, ensure_ascii=False, indent=2), 
            encoding="utf-8"
        )

        logger.info(f"persist: {result.content_hash} → {storage_path} ({len(result.tables)} tables)")
        return str(storage_path)
