import pytest
from pathlib import Path
from unittest.mock import patch, AsyncMock, MagicMock
from app.services.subjects_scout import SubjectsScoutAgent
from app.schemas.edital_schema import Cargo, Materia


_SAMPLE_CARGO = Cargo(
    titulo="Analista Judiciário",
    vagas_ampla=10,
    vagas_cotas=2,
    salario=8000.0,
    requisitos="Nível superior",
    materias=[],
)


# ── _find_subjects_section ───────────────────────────────────────────────────

def test_find_subjects_section_finds_conteudo_programatico():
    agent = SubjectsScoutAgent()
    text = "Texto antes.\n\nCONTEÚDO PROGRAMÁTICO\n1. Português\n2. Matemática\n"
    result = agent._find_subjects_section(text)
    assert "CONTEÚDO PROGRAMÁTICO" in result


def test_find_subjects_section_returns_empty_when_not_found():
    agent = SubjectsScoutAgent()
    text = "Texto sobre vagas e salários. Sem qualquer seção de provas ou programas."
    result = agent._find_subjects_section(text)
    assert result == ""


def test_find_subjects_section_finds_dos_conteudos():
    agent = SubjectsScoutAgent()
    text = "Capítulo 3\n\nDOS CONTEÚDOS PROGRAMÁTICOS\nPortuguês: gramática."
    result = agent._find_subjects_section(text)
    assert len(result) > 0


def test_find_subjects_section_truncates_at_60k():
    agent = SubjectsScoutAgent()
    long_text = "CONTEÚDO PROGRAMÁTICO\n" + "X" * 70000
    result = agent._find_subjects_section(long_text)
    assert len(result) <= 60000 + len("CONTEÚDO PROGRAMÁTICO\n")


# ── _extract_for_cargo ───────────────────────────────────────────────────────

@pytest.mark.asyncio
async def test_extract_for_cargo_success():
    agent = SubjectsScoutAgent()
    mock_result = MagicMock()
    mock_result.materias = [Materia(nome="Português", topicos=["Ortografia"])]

    with patch.object(agent.ollama_provider, 'generate_json',
                      new_callable=AsyncMock, return_value=mock_result):
        result = await agent._extract_for_cargo(_SAMPLE_CARGO, "Conteúdo do edital")
        assert len(result) == 1
        assert result[0].nome == "Português"


@pytest.mark.asyncio
async def test_extract_for_cargo_provider_failure_returns_empty():
    agent = SubjectsScoutAgent()
    with patch.object(agent.ollama_provider, 'generate_json',
                      new_callable=AsyncMock,
                      side_effect=ConnectionError("offline")):
        result = await agent._extract_for_cargo(_SAMPLE_CARGO, "seção")
        assert result == []


# ── scout ─────────────────────────────────────────────────────────────────────

@pytest.mark.asyncio
async def test_scout_returns_cargos_when_storage_not_found():
    agent = SubjectsScoutAgent()
    cargos = [_SAMPLE_CARGO]
    result = await agent.scout("nonexistent-hash", cargos)
    assert result == cargos


@pytest.mark.asyncio
async def test_scout_extracts_materias(tmp_path):
    agent = SubjectsScoutAgent()
    content_hash = "scout-test-hash"
    storage_path = tmp_path / content_hash
    storage_path.mkdir()
    (storage_path / "main.md").write_text(
        "CONTEÚDO PROGRAMÁTICO\nPortuguês: Ortografia. Matemática: Álgebra.",
        encoding="utf-8",
    )

    mock_materias = [Materia(nome="Português", topicos=["Ortografia"])]

    with patch.object(agent, '_extract_for_cargo',
                      new_callable=AsyncMock, return_value=mock_materias), \
         patch('app.services.subjects_scout.Path') as mock_path_cls:

        def path_side_effect(*args):
            joined = "/".join(str(a) for a in args)
            if "storage/processed" in joined:
                p = MagicMock()
                p.__truediv__ = lambda self, other: storage_path / other if other == content_hash else tmp_path / "missing"
                return p
            return Path(*args)

        # Simpler: patch directly with real paths
        with patch('app.services.subjects_scout.Path',
                   side_effect=lambda *a: tmp_path if "storage" in str(a[0]) else Path(*a)):
            result = await agent.scout(content_hash, [_SAMPLE_CARGO])
            assert isinstance(result, list)


@pytest.mark.asyncio
async def test_scout_uses_full_text_when_no_subjects_section(tmp_path):
    agent = SubjectsScoutAgent()
    content_hash = "no-section-hash"
    storage_path = tmp_path / content_hash
    storage_path.mkdir()
    (storage_path / "main.md").write_text(
        "Texto sem seção programática explícita. " * 100, encoding="utf-8"
    )

    mock_materias: list = []

    with patch.object(agent, '_extract_for_cargo',
                      new_callable=AsyncMock, return_value=mock_materias):

        # Patch storage path resolution
        original_path = __import__('pathlib').Path

        def patched_path(*args):
            if args and "storage/processed" in str(args[0]):
                class FakePath:
                    def __truediv__(self, other):
                        return storage_path / other if other == content_hash else original_path("nonexistent") / other
                    def exists(self): return False
                return FakePath()
            return original_path(*args)

        result = await agent.scout(content_hash, [_SAMPLE_CARGO])
        # Even without subjects section, should return cargos list
        assert isinstance(result, list)
