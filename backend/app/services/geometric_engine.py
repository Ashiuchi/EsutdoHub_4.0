import logging
import re
import statistics
from dataclasses import dataclass, field

import fitz

logger = logging.getLogger(__name__)

# ---------------------------------------------------------------------------
# Constantes
# ---------------------------------------------------------------------------

_FLAG_ITALIC = 1 << 1
_FLAG_BOLD   = 1 << 4

_LINE_Y_TOLERANCE = 3.0
_MARGIN_LOW_PCT   = 0.10
_MARGIN_HIGH_PCT  = 0.90

_H1_SIZE_RATIO = 1.40
_H2_SIZE_RATIO = 1.15
_H3_FILL_MAX   = 0.60

_FULL_LINE_RATIO  = 0.94
_NOISE_ZONE_PCT   = 0.10
_ALLCAPS_FILL_MAX = 0.92  # fill máximo para linha ALL-CAPS ser detectada como heading

# Padrões de início de subitem numerado ou alfabético (ex: "1.4 texto", "a) texto")
_ITEM_START_RE = re.compile(r'^\d[\d.]*\s|^[a-z]\)\s')

# Merge de tabelas adjacentes
_TABLE_X_TOL   = 2.0   # pt — tolerância em x0/x1 para considerar mesma coluna
_TABLE_Y_GAP   = 5.0   # pt — gap vertical máximo entre tabelas mescladas
_TABLE_COL_TOL = 3.0   # pt — tolerância nas posições de divisórias de coluna


# ---------------------------------------------------------------------------
# Funções auxiliares de módulo
# ---------------------------------------------------------------------------

def _clean_text(text: str) -> str:
    return re.sub(r' {2,}', ' ', text.replace('\xa0', ' ')).strip()


def _format_spans(spans: list) -> str:
    parts = []
    for s in spans:
        t = _clean_text(s.text)
        if not t:
            continue
        if s.is_bold and s.is_italic:
            parts.append(f"***{t}***")
        elif s.is_bold:
            parts.append(f"**{t}**")
        elif s.is_italic:
            parts.append(f"*{t}*")
        else:
            parts.append(t)
    return " ".join(parts)


def _heading_level(line, layout) -> int:
    text = line.text.strip()
    if len(text) < 3:
        return 0
    # Linha começando com minúscula é continuação de sentença, nunca título
    if text[0].islower():
        return 0
    size_ratio = line.dominant_font_size / max(layout.body_font_size, 1.0)
    fill = line.width / max(layout.usable_width, 1.0)
    if line.is_bold:
        if size_ratio >= _H1_SIZE_RATIO:
            return 1
        if size_ratio >= _H2_SIZE_RATIO:
            return 2
        if fill < _H3_FILL_MAX and not text.endswith((';', ',')):
            return 3
    # ALL-CAPS sem bold (ex: Cebraspe/INSS — títulos em caixa alta com fonte normal)
    if (text.isupper() and len(text) > 8 and fill < _ALLCAPS_FILL_MAX
            and not text.endswith((';', ','))):
        if size_ratio >= _H2_SIZE_RATIO:
            return 2
        return 3
    return 0


def _rows_to_md(rows: list) -> str:
    if not rows:
        return ""
    cleaned = [
        [re.sub(r'\s+', ' ', str(c or "")).strip() for c in row]
        for row in rows
    ]
    n_cols = max((len(r) for r in cleaned), default=0)
    if n_cols == 0:
        return ""
    padded = [r + [""] * (n_cols - len(r)) for r in cleaned]
    header = "| " + " | ".join(padded[0]) + " |"
    sep    = "| " + " | ".join(["---"] * n_cols) + " |"
    body   = "\n".join("| " + " | ".join(row) + " |" for row in padded[1:])
    return "\n".join(filter(None, [header, sep, body]))


# ---------------------------------------------------------------------------
# Table merge geométrico
# ---------------------------------------------------------------------------

def _col_dividers(tbl) -> list[float]:
    """Posições x das divisórias de coluna derivadas dos bboxes das células."""
    xs: set[float] = set()
    for cell in tbl.cells:
        # cells são tuplas (x0, y0, x1, y1)
        xs.add(round(float(cell[0]), 1))
        xs.add(round(float(cell[2]), 1))
    return sorted(xs)


@dataclass
class _TableGroup:
    y0:       float
    y1:       float
    md:       str          # markdown renderizado da tabela mesclada
    n_source: int          # quantas tabelas fitz foram mescladas


def _build_table_groups(
    tables: list,
    x_tol:   float = _TABLE_X_TOL,
    y_gap:   float = _TABLE_Y_GAP,
    col_tol: float = _TABLE_COL_TOL,
) -> list[_TableGroup]:
    """Agrupa tabelas adjacentes com mesmo alinhamento geométrico de colunas."""
    if not tables:
        return []

    by_y = sorted(tables, key=lambda t: t.bbox[1])
    raw_groups: list[list] = [[by_y[0]]]

    for tbl in by_y[1:]:
        prev = raw_groups[-1][-1]
        gap  = tbl.bbox[1] - prev.bbox[3]

        # Critério 1: gap vertical pequeno
        if gap > y_gap:
            raw_groups.append([tbl])
            continue

        # Critério 2: mesmas bordas horizontais
        if (abs(tbl.bbox[0] - prev.bbox[0]) > x_tol or
                abs(tbl.bbox[2] - prev.bbox[2]) > x_tol):
            raw_groups.append([tbl])
            continue

        # Critério 3: mesmas posições de divisórias de coluna
        cols_prev = _col_dividers(prev)
        cols_curr = _col_dividers(tbl)
        if (not cols_prev or not cols_curr or
                len(cols_prev) != len(cols_curr) or
                not all(abs(a - b) <= col_tol
                        for a, b in zip(cols_prev, cols_curr))):
            raw_groups.append([tbl])
            continue

        raw_groups[-1].append(tbl)

    result: list[_TableGroup] = []
    for group in raw_groups:
        all_rows: list[list] = []
        header_row: list | None = None

        for i, tbl in enumerate(group):
            rows = tbl.extract() or []
            if i == 0:
                header_row = rows[0] if rows else None
                all_rows.extend(rows)
            else:
                # Pula linha de cabeçalho duplicada em tabelas subsequentes
                if header_row and rows and rows[0] == header_row:
                    rows = rows[1:]
                all_rows.extend(rows)

        result.append(_TableGroup(
            y0=group[0].bbox[1],
            y1=group[-1].bbox[3],
            md=_rows_to_md(all_rows),
            n_source=len(group),
        ))

    merged_count = sum(g.n_source for g in result) - len(result)
    if merged_count > 0:
        logger.debug("_build_table_groups: %d grupos ← %d tabelas (%d mescladas)",
                     len(result), sum(g.n_source for g in result), merged_count)

    return result


# ---------------------------------------------------------------------------
# Dataclasses de layout
# ---------------------------------------------------------------------------

@dataclass
class SpanInfo:
    text:      str
    font_size: float
    is_bold:   bool
    is_italic: bool
    bbox:      tuple[float, float, float, float]


@dataclass
class LineInfo:
    spans:    list[SpanInfo] = field(default_factory=list)
    y_center: float = 0.0
    x0:       float = 0.0
    x1:       float = 0.0

    @property
    def text(self) -> str:
        return "".join(s.text for s in self.spans)

    @property
    def dominant_font_size(self) -> float:
        if not self.spans:
            return 0.0
        return max(self.spans, key=lambda s: len(s.text)).font_size

    @property
    def is_bold(self) -> bool:
        bold_len  = sum(len(s.text) for s in self.spans if s.is_bold)
        total_len = sum(len(s.text) for s in self.spans)
        return bold_len > total_len / 2 if total_len else False

    @property
    def is_italic(self) -> bool:
        italic_len = sum(len(s.text) for s in self.spans if s.is_italic)
        total_len  = sum(len(s.text) for s in self.spans)
        return italic_len > total_len / 2 if total_len else False

    @property
    def width(self) -> float:
        return self.x1 - self.x0


@dataclass
class PageLayout:
    page_num:       int
    width:          float
    height:         float
    usable_x0:      float
    usable_x1:      float
    usable_width:   float
    body_font_size: float
    lines:          list[LineInfo] = field(default_factory=list)


# ---------------------------------------------------------------------------
# GeometricEngine
# ---------------------------------------------------------------------------

class GeometricEngine:
    """Extrai e converte PDF para Markdown usando coordenadas geométricas."""

    def extract_page_layout(self, page: fitz.Page) -> PageLayout:
        raw   = page.get_text("dict", flags=fitz.TEXT_PRESERVE_WHITESPACE)
        page_w: float = raw["width"]
        page_h: float = raw["height"]

        all_fitz_lines: list[dict] = []
        for block in raw["blocks"]:
            if block["type"] != 0:
                continue
            for fitz_line in block["lines"]:
                if fitz_line["spans"]:
                    all_fitz_lines.append(fitz_line)

        proto_lines: list[tuple[float, list[SpanInfo]]] = []
        for fitz_line in all_fitz_lines:
            lb = fitz_line["bbox"]
            y_center = (lb[1] + lb[3]) / 2.0
            spans = []
            for sp in fitz_line["spans"]:
                if not sp["text"].strip():
                    continue
                flags = sp.get("flags", 0)
                spans.append(SpanInfo(
                    text=sp["text"],
                    font_size=sp["size"],
                    is_bold=bool(flags & _FLAG_BOLD),
                    is_italic=bool(flags & _FLAG_ITALIC),
                    bbox=(sp["bbox"][0], sp["bbox"][1],
                          sp["bbox"][2], sp["bbox"][3]),
                ))
            if spans:
                proto_lines.append((y_center, spans))

        proto_lines.sort(key=lambda t: t[0])
        grouped: list[LineInfo] = []

        for y_c, spans in proto_lines:
            if grouped and abs(y_c - grouped[-1].y_center) <= _LINE_Y_TOLERANCE:
                target = grouped[-1]
                target.spans.extend(spans)
                target.spans.sort(key=lambda s: s.bbox[0])
                target.x0 = min(s.bbox[0] for s in target.spans)
                target.x1 = max(s.bbox[2] for s in target.spans)
                target.y_center = (target.y_center + y_c) / 2.0
            else:
                x0 = min(s.bbox[0] for s in spans)
                x1 = max(s.bbox[2] for s in spans)
                grouped.append(LineInfo(
                    spans=sorted(spans, key=lambda s: s.bbox[0]),
                    y_center=y_c,
                    x0=x0,
                    x1=x1,
                ))

        body_x0s = [ln.x0 for ln in grouped if len(ln.text.strip()) > 5]
        body_x1s = [ln.x1 for ln in grouped if len(ln.text.strip()) > 5]

        if len(body_x0s) >= 4:
            lo = int(len(body_x0s) * _MARGIN_LOW_PCT)
            hi = int(len(body_x1s) * _MARGIN_HIGH_PCT)
            usable_x0 = sorted(body_x0s)[lo]
            usable_x1 = sorted(body_x1s)[hi]
        else:
            usable_x0 = 50.0
            usable_x1 = page_w - 50.0

        usable_width = max(usable_x1 - usable_x0, 1.0)

        font_samples: list[float] = []
        for ln in grouped:
            for sp in ln.spans:
                font_samples.extend([sp.font_size] * max(len(sp.text), 1))
        body_font_size = statistics.median(font_samples) if font_samples else 12.0

        layout = PageLayout(
            page_num=page.number,
            width=page_w,
            height=page_h,
            usable_x0=usable_x0,
            usable_x1=usable_x1,
            usable_width=usable_width,
            body_font_size=body_font_size,
            lines=grouped,
        )
        logger.debug(
            "Page %d: %.0fx%.0f pt | usable=[%.1f,%.1f] (%.0f pt) | "
            "body_font=%.1fpt | %d lines",
            layout.page_num, layout.width, layout.height,
            layout.usable_x0, layout.usable_x1, layout.usable_width,
            layout.body_font_size, len(layout.lines),
        )
        return layout

    def to_markdown(self, page: fitz.Page) -> str:
        """Converte uma página para Markdown com tabelas inlineadas."""
        layout    = self.extract_page_layout(page)
        noise_top = layout.height * _NOISE_ZONE_PCT
        noise_bot = layout.height * (1.0 - _NOISE_ZONE_PCT)

        # Detecção e merge geométrico de tabelas
        table_groups: list[_TableGroup] = []
        try:
            raw_tables = page.find_tables().tables
            table_groups = _build_table_groups(raw_tables)
            if table_groups:
                logger.debug(
                    "Page %d: %d grupo(s) de tabela | fontes fitz: %d",
                    page.number, len(table_groups),
                    sum(g.n_source for g in table_groups),
                )
        except Exception as exc:
            logger.warning("find_tables falhou na página %d: %s", page.number, exc)

        emitted: set[int] = set()
        para_parts: list[str] = []
        out: list[str] = []

        def _flush() -> None:
            if para_parts:
                out.append(" ".join(para_parts))
                out.append("")
                para_parts.clear()

        for line in layout.lines:
            if line.y_center < noise_top or line.y_center > noise_bot:
                continue

            # Verifica pertencimento a algum grupo de tabela
            tg_idx = next(
                (i for i, tg in enumerate(table_groups)
                 if tg.y0 <= line.y_center <= tg.y1),
                None,
            )
            if tg_idx is not None:
                if tg_idx not in emitted:
                    _flush()
                    tg = table_groups[tg_idx]
                    if tg.md:
                        out.append(tg.md)
                        out.append("")
                    emitted.add(tg_idx)
                continue

            text = _format_spans(line.spans)
            if not text:
                continue

            fill  = line.width / max(layout.usable_width, 1.0)
            level = _heading_level(line, layout)

            if level > 0:
                _flush()
                clean = re.sub(r'\*+', '', text).strip()
                out.append(f"{'#' * level} {clean}")
                out.append("")
            elif fill >= _FULL_LINE_RATIO:
                if _ITEM_START_RE.match(text) and para_parts:
                    _flush()
                para_parts.append(text.rstrip("- "))
            else:
                para_parts.append(text)
                _flush()

        _flush()
        md = "\n".join(out)
        md = re.sub(r'\n{3,}', '\n\n', md).strip()
        logger.debug("Page %d → %d chars markdown", page.number, len(md))
        return md

    def document_to_markdown(self, path: str) -> str:
        """Processa um PDF inteiro e retorna o Markdown completo."""
        doc = fitz.open(path)
        pages_md: list[str] = []
        n_table_groups = 0
        try:
            for page in doc:
                page_md = self.to_markdown(page)
                if page_md.strip():
                    pages_md.append(page_md)
        finally:
            doc.close()

        full_md = "\n\n".join(pages_md)
        full_md = re.sub(r'\n{3,}', '\n\n', full_md).strip()
        logger.info(
            "GeometricEngine: %s → %d chars | %d páginas com conteúdo",
            path, len(full_md), len(pages_md),
        )
        return full_md
