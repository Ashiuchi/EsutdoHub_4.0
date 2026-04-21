import json
import logging
import re
from typing import Dict, Tuple

logger = logging.getLogger(__name__)

# Matches one or more consecutive lines that start (after optional whitespace) with |
_TABLE_RE = re.compile(r'(?m)(?:^[ \t]*\|[^\n]*(?:\n|$))+')


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
