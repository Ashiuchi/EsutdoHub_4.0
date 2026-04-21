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
