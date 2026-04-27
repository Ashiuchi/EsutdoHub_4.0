import pytest
from app.services.subtractive_service import SubtractiveAgent

SAMPLE_TABLE = """\
Antes da tabela.

| Cargo | Vagas | Salário |
|-------|-------|---------|
| Analista | 10 | R$ 5.000 |
| Técnico | 20 | R$ 3.000 |

Depois da tabela.
"""

def test_strip_tables_removes_table_block():
    agent = SubtractiveAgent()
    stripped, fragments = agent.strip_tables(SAMPLE_TABLE)

    assert "| Cargo |" not in stripped
    assert "|-------|" not in stripped
    assert "Antes da tabela." in stripped
    assert "Depois da tabela." in stripped


def test_strip_tables_creates_marker():
    agent = SubtractiveAgent()
    stripped, fragments = agent.strip_tables(SAMPLE_TABLE)

    assert "[[FRAGMENT_TABLE_0]]" in stripped


def test_strip_tables_stores_fragment():
    agent = SubtractiveAgent()
    _, fragments = agent.strip_tables(SAMPLE_TABLE)

    assert "FRAGMENT_TABLE_0" in fragments
    assert "| Cargo |" in fragments["FRAGMENT_TABLE_0"]


def test_strip_tables_multiple_tables():
    md = "| A |\n|---|\n| 1 |\n\nTexto\n\n| B |\n|---|\n| 2 |\n"
    agent = SubtractiveAgent()
    stripped, fragments = agent.strip_tables(md)

    assert "FRAGMENT_TABLE_0" in fragments
    assert "FRAGMENT_TABLE_1" in fragments
    assert "[[FRAGMENT_TABLE_0]]" in stripped
    assert "[[FRAGMENT_TABLE_1]]" in stripped


def test_strip_tables_no_tables_unchanged():
    md = "Texto simples sem tabelas.\nSegunda linha."
    agent = SubtractiveAgent()
    stripped, fragments = agent.strip_tables(md)

    assert stripped == md
    assert fragments == {}


# ── _extract_programmatic_sections ──────────────────────────────────────────

_EDITAL_WITH_PROG = """\
EDITAL Nº 001/2026

1. DAS DISPOSIÇÕES GERAIS
Salário: R$ 5.000,00. Inscrições: 01/04/2026.

| Cargo | Vagas |
|-------|-------|
| Analista | 10 |

2. CONTEÚDO PROGRAMÁTICO

CARGO: ANALISTA JUDICIÁRIO

LÍNGUA PORTUGUESA
1. Interpretação de textos.
2. Ortografia oficial.

MATEMÁTICA
1. Operações fundamentais.
2. Porcentagem e juros.

3. DAS DISPOSIÇÕES FINAIS
Local de prova: a definir.
"""

_EDITAL_PROGRAMA_DE_PROVAS = """\
EDITAL

Informações gerais sobre o certame.

PROGRAMA DE PROVAS

CONHECIMENTOS GERAIS
1. Língua Portuguesa: interpretação.

CONHECIMENTOS ESPECÍFICOS
1. Direito Administrativo.
"""

_EDITAL_ANEXO = """\
Texto inicial sem conteúdo programático.

ANEXO II - CONTEÚDO PROGRAMÁTICO

DIREITO CONSTITUCIONAL
1. Princípios fundamentais.
2. Direitos e garantias.
"""


def test_extract_programmatic_sections_finds_conteudo_programatico():
    agent = SubtractiveAgent()
    result = agent._extract_programmatic_sections(_EDITAL_WITH_PROG)
    assert "LÍNGUA PORTUGUESA" in result
    assert "MATEMÁTICA" in result


def test_extract_programmatic_sections_excludes_preamble():
    agent = SubtractiveAgent()
    result = agent._extract_programmatic_sections(_EDITAL_WITH_PROG)
    assert "DAS DISPOSIÇÕES GERAIS" not in result


def test_extract_programmatic_sections_finds_programa_de_provas():
    agent = SubtractiveAgent()
    result = agent._extract_programmatic_sections(_EDITAL_PROGRAMA_DE_PROVAS)
    assert "CONHECIMENTOS GERAIS" in result
    assert "CONHECIMENTOS ESPECÍFICOS" in result


def test_extract_programmatic_sections_finds_anexo():
    agent = SubtractiveAgent()
    result = agent._extract_programmatic_sections(_EDITAL_ANEXO)
    assert "DIREITO CONSTITUCIONAL" in result


def test_extract_programmatic_sections_returns_empty_when_not_found():
    agent = SubtractiveAgent()
    text = "Texto sobre vagas e salários. Apenas datas e números."
    result = agent._extract_programmatic_sections(text)
    assert result == ""


# ── process() → clean_md ────────────────────────────────────────────────────

def test_process_clean_md_contains_programmatic_content():
    agent = SubtractiveAgent()
    result = agent.process(_EDITAL_WITH_PROG)
    assert "LÍNGUA PORTUGUESA" in result.clean_md


def test_process_clean_md_excludes_preamble_when_section_found():
    agent = SubtractiveAgent()
    result = agent.process(_EDITAL_WITH_PROG)
    assert "DAS DISPOSIÇÕES GERAIS" not in result.clean_md


def test_process_clean_md_strips_tables_inside_programmatic_section():
    md = "CONTEÚDO PROGRAMÁTICO\n\n| Matéria | Tópico |\n|---------|--------|\n| Português | Gramática |\n\nLíngua Portuguesa: gramática."
    agent = SubtractiveAgent()
    result = agent.process(md)
    assert "| Matéria |" not in result.clean_md
    assert "Língua Portuguesa" in result.clean_md


def test_process_clean_md_falls_back_to_full_text_when_no_section():
    md = "Texto corrido sem seção programática específica.\nMais conteúdo."
    agent = SubtractiveAgent()
    result = agent.process(md)
    assert "Texto corrido" in result.clean_md
    assert len(result.clean_md) > 0


def test_process_main_md_still_has_full_document():
    agent = SubtractiveAgent()
    result = agent.process(_EDITAL_WITH_PROG)
    assert "DAS DISPOSIÇÕES GERAIS" in result.main_md


def test_process_data_md_contains_tables():
    agent = SubtractiveAgent()
    result = agent.process(_EDITAL_WITH_PROG)
    assert "Cargo" in result.data_md or "Vagas" in result.data_md


# ── clean.md — tabular-only editais (IBFC pattern) ──────────────────────────

def test_process_clean_md_includes_table_when_programmatic_in_cell():
    """Table whose cell contains 'CONTEÚDO PROGRAMÁTICO' must survive into clean.md."""
    md = (
        "| CONTEÚDO PROGRAMÁTICO | Cargo |\n"
        "|---|---|\n"
        "| Língua Portuguesa | Analista |\n"
        "| Matemática | Assistente |\n"
    )
    agent = SubtractiveAgent()
    result = agent.process(md)
    assert "Língua Portuguesa" in result.clean_md


def test_process_clean_md_strips_regular_table_keeps_programmatic_table():
    """Regular table inside programmatic section stripped; table-with-marker kept."""
    md = (
        "| CONTEÚDO PROGRAMÁTICO | Área |\n"
        "|---|---|\n"
        "| Língua Portuguesa | Analista |\n"
        "\n"
        "| Cargo | Vagas |\n"
        "|---|---|\n"
        "| Analista | 10 |\n"
    )
    agent = SubtractiveAgent()
    result = agent.process(md)
    assert "Língua Portuguesa" in result.clean_md
    assert "Vagas" not in result.clean_md
