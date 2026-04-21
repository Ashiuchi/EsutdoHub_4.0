import json
import logging
import re
from typing import Dict, Tuple

logger = logging.getLogger(__name__)

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

        reduction = len(md) - len(stripped)
        logger.info(
            f"SubtractiveAgent.process: {len(md)} → {len(stripped)} chars "
            f"(−{reduction}, {len(table_fragments)} tables, "
            f"{len(pattern_fragments)} patterns)"
        )
        return stripped, all_fragments
