import pytest
from pathlib import Path
from app.services.subjects_scout import SubjectsScoutAgent


def test_build_table_fallback_context_concatenates_all_files(tmp_path):
    (tmp_path / "tabela_0.md").write_text("| Matéria | Tópico |\n|---|---|\n| Matemática | Álgebra |\n")
    (tmp_path / "tabela_1.md").write_text("| Cargo | Área |\n|---|---|\n| Analista | TI |\n")
    table_files = sorted(tmp_path.glob("*.md"))

    agent = SubjectsScoutAgent()
    ctx = agent._build_table_fallback_context(table_files)

    assert "Matemática" in ctx
    assert "Álgebra" in ctx
    assert "Analista" in ctx


def test_build_table_fallback_context_empty_when_no_files():
    agent = SubjectsScoutAgent()
    ctx = agent._build_table_fallback_context([])
    assert ctx == ""


def test_build_table_fallback_context_respects_limit(tmp_path):
    (tmp_path / "big.md").write_text("A" * 1000)
    table_files = list(tmp_path.glob("*.md"))

    agent = SubjectsScoutAgent()
    ctx = agent._build_table_fallback_context(table_files, limit=500)
    assert len(ctx) <= 500
