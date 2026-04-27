import pytest
import json
from pathlib import Path
from app.services.subtractive_service import SubtractiveAgent, StorageResult

def test_persist_creates_structure(tmp_path):
    agent = SubtractiveAgent()
    result = StorageResult(
        content_hash="test_hash_123",
        main_md="# Teste\nConteúdo enxuto.",
        data_md="| A | B |\n|---|---|\n| 1 | 2 |",
        clean_md="Conteúdo programático enxuto.",
        tables={"FRAGMENT_TABLE_0": "| A | B |\n|---|---|\n| 1 | 2 |"},
        patterns={"dates": ["22/04/2026"], "money": ["R$ 1.500,00"]}
    )

    path_str = agent.persist(result, storage_base=tmp_path)
    storage_path = Path(path_str)

    assert storage_path.exists()
    assert (storage_path / "main.md").read_text() == result.main_md
    assert (storage_path / "data.md").read_text() == result.data_md
    assert (storage_path / "clean.md").read_text() == result.clean_md
    assert (storage_path / "tables" / "tabela_0.md").exists()

    metadata = json.loads((storage_path / "metadata.json").read_text())
    assert metadata["content_hash"] == "test_hash_123"
    assert metadata["table_count"] == 1
    assert "22/04/2026" in metadata["patterns"]["dates"]

def test_persist_multiple_tables(tmp_path):
    agent = SubtractiveAgent()
    result = StorageResult(
        content_hash="multi_table",
        main_md="...",
        data_md="",
        clean_md="",
        tables={
            "FRAGMENT_TABLE_0": "table 0",
            "FRAGMENT_TABLE_1": "table 1"
        }
    )

    agent.persist(result, storage_base=tmp_path)
    assert (tmp_path / "multi_table" / "tables" / "tabela_0.md").exists()
    assert (tmp_path / "multi_table" / "tables" / "tabela_1.md").exists()
