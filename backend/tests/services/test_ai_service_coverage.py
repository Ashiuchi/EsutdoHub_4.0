import pytest
from unittest.mock import patch, AsyncMock, MagicMock
from app.services.ai_service import AIService
from app.schemas.edital_schema import EditalGeral, Cargo, Materia

CHUNK_THRESHOLD = 15_000

_MOCK_EDITAL = EditalGeral(
    orgao="Tribunal X",
    banca="CESPE",
    data_prova=None,
    periodo_inscricao=None,
    link_edital=None,
    cargos=[
        Cargo(
            titulo="Analista Judiciário",
            vagas_ampla=10,
            vagas_cotas=2,
            salario=8000.0,
            requisitos="Nível superior",
            materias=[Materia(nome="Português", topicos=["Ortografia", "Sintaxe"])],
        )
    ],
)


# ── _merge_materias ───────────────────────────────────────────────────────────

def test_merge_materias_deduplicates_by_name():
    existing = [Materia(nome="Português", topicos=["Ortografia"])]
    incoming = [
        Materia(nome="Português", topicos=["Sintaxe"]),
        Materia(nome="Matemática", topicos=["Álgebra"]),
    ]
    result = AIService._merge_materias(existing, incoming)
    names = [m.nome for m in result]
    assert names.count("Português") == 1
    assert "Matemática" in names


def test_merge_materias_keeps_existing_when_duplicate():
    existing = [Materia(nome="Português", topicos=["Ortografia"])]
    incoming = [Materia(nome="Português", topicos=["Sintaxe"])]
    result = AIService._merge_materias(existing, incoming)
    assert result[0].topicos == ["Ortografia"]


def test_merge_materias_empty_lists():
    assert AIService._merge_materias([], []) == []


# ── _merge_cargos ─────────────────────────────────────────────────────────────

def test_merge_cargos_merges_materias_for_same_title():
    base = [
        Cargo(titulo="Analista", vagas_ampla=5, vagas_cotas=0, salario=3000.0,
              requisitos="", materias=[Materia(nome="Português", topicos=["A"])])
    ]
    incoming = [
        Cargo(titulo="Analista", vagas_ampla=5, vagas_cotas=0, salario=3000.0,
              requisitos="", materias=[Materia(nome="Matemática", topicos=["B"])])
    ]
    result = AIService._merge_cargos(base, incoming)
    assert len(result) == 1
    names = [m.nome for m in result[0].materias]
    assert "Português" in names
    assert "Matemática" in names


def test_merge_cargos_adds_new_cargo():
    base = [Cargo(titulo="Analista", vagas_ampla=5, vagas_cotas=0,
                  salario=3000.0, requisitos="", materias=[])]
    incoming = [Cargo(titulo="Técnico", vagas_ampla=3, vagas_cotas=0,
                      salario=2000.0, requisitos="", materias=[])]
    result = AIService._merge_cargos(base, incoming)
    assert len(result) == 2


def test_merge_cargos_empty():
    assert AIService._merge_cargos([], []) == []


# ── _create_edital_sync / _persist_cargos_sync ───────────────────────────────

def test_create_edital_sync_success():
    service = AIService()
    mock_db = MagicMock()
    mock_edital_db = MagicMock()
    mock_edital_db.id = 42

    with patch('app.services.ai_service.SessionLocal', return_value=mock_db), \
         patch('app.services.ai_service.db_models.Edital', return_value=mock_edital_db):
        result = service._create_edital_sync(_MOCK_EDITAL)
        # id is whatever the mock returns
        assert result is not None
        mock_db.commit.assert_called_once()


def test_create_edital_sync_db_failure_returns_none():
    service = AIService()
    mock_db = MagicMock()
    mock_db.commit.side_effect = Exception("DB offline")

    with patch('app.services.ai_service.SessionLocal', return_value=mock_db), \
         patch('app.services.ai_service.db_models.Edital', return_value=MagicMock()):
        result = service._create_edital_sync(_MOCK_EDITAL)
        assert result is None
        mock_db.rollback.assert_called_once()


def test_persist_cargos_sync_inserts_cargo():
    service = AIService()
    mock_db = MagicMock()
    mock_cargo_db = MagicMock()
    mock_cargo_db.id = 1
    mock_materia_db = MagicMock()
    mock_materia_db.id = 10

    known: set = set()
    with patch('app.services.ai_service.SessionLocal', return_value=mock_db), \
         patch('app.services.ai_service.db_models.Cargo', return_value=mock_cargo_db), \
         patch('app.services.ai_service.db_models.Materia', return_value=mock_materia_db), \
         patch('app.services.ai_service.db_models.Topico', return_value=MagicMock()):
        result = service._persist_cargos_sync(1, _MOCK_EDITAL.cargos, known)
        assert len(result) == 1
        assert "Analista Judiciário" in known


def test_persist_cargos_sync_skips_known_titulo():
    service = AIService()
    known = {"Analista Judiciário"}
    mock_db = MagicMock()
    with patch('app.services.ai_service.SessionLocal', return_value=mock_db):
        result = service._persist_cargos_sync(1, _MOCK_EDITAL.cargos, known)
        assert result == []
        mock_db.commit.assert_not_called()


def test_persist_cargos_sync_db_failure_returns_empty():
    service = AIService()
    mock_db = MagicMock()
    mock_db.flush.side_effect = Exception("DB error")
    known: set = set()
    with patch('app.services.ai_service.SessionLocal', return_value=mock_db), \
         patch('app.services.ai_service.db_models.Cargo', return_value=MagicMock(id=1)):
        result = service._persist_cargos_sync(1, _MOCK_EDITAL.cargos, known)
        assert result == []
        mock_db.rollback.assert_called_once()


# ── extract_edital_data — single-pass failure ─────────────────────────────────

@pytest.mark.asyncio
async def test_extract_single_pass_all_providers_fail():
    service = AIService()
    with patch.object(service, '_extract_from_chunk', new_callable=AsyncMock, return_value=None):
        with pytest.raises(RuntimeError, match="Todos os providers LLM falharam na extração"):
            await service.extract_edital_data(md_content="texto curto")


# ── extract_edital_data — chunked path ───────────────────────────────────────

@pytest.mark.asyncio
async def test_extract_chunked_all_chunks_succeed():
    service = AIService()
    large_content = "# Edital TRT\n" + "Conteúdo relevante.\n" * 900

    with patch.object(service, '_extract_from_chunk', new_callable=AsyncMock,
                      return_value=_MOCK_EDITAL) as mock_extract, \
         patch.object(service, '_create_edital_db', new_callable=AsyncMock,
                      return_value=None) as mock_create, \
         patch.object(service, '_persist_and_broadcast', new_callable=AsyncMock):

        result = await service.extract_edital_data(md_content=large_content)

        assert result.orgao == "Tribunal X"
        assert mock_extract.call_count >= 2
        mock_create.assert_called_once()


@pytest.mark.asyncio
async def test_extract_chunked_first_chunk_fails_fallback():
    service = AIService()
    large_content = "# Edital\n" + "X" * 16000

    call_count = 0

    async def side_effect(chunk):
        nonlocal call_count
        call_count += 1
        return None if call_count == 1 else _MOCK_EDITAL

    with patch.object(service, '_extract_from_chunk', side_effect=side_effect), \
         patch.object(service, '_create_edital_db', new_callable=AsyncMock,
                      return_value=None), \
         patch.object(service, '_persist_and_broadcast', new_callable=AsyncMock):

        result = await service.extract_edital_data(md_content=large_content)
        assert result.orgao == "Tribunal X"


@pytest.mark.asyncio
async def test_extract_chunked_all_chunks_fail_raises():
    service = AIService()
    large_content = "# Edital\n" + "X" * 16000

    with patch.object(service, '_extract_from_chunk', new_callable=AsyncMock,
                      return_value=None):
        with pytest.raises(RuntimeError, match="Extração em chunks não produziu cargos"):
            await service.extract_edital_data(md_content=large_content)


@pytest.mark.asyncio
async def test_extract_chunked_merges_cargos_across_chunks():
    service = AIService()
    large_content = "# Edital\n" + "linha\n" * 2600  # ~15610 chars, exceeds CHUNK_THRESHOLD

    edital_chunk1 = EditalGeral(
        orgao="Org A", banca="Banca", data_prova=None,
        periodo_inscricao=None, link_edital=None,
        cargos=[Cargo(titulo="Analista", vagas_ampla=5, vagas_cotas=0,
                      salario=3000.0, requisitos="", materias=[])],
    )
    edital_chunk2 = EditalGeral(
        orgao="Org A", banca="Banca", data_prova=None,
        periodo_inscricao=None, link_edital=None,
        cargos=[Cargo(titulo="Técnico", vagas_ampla=3, vagas_cotas=0,
                      salario=2000.0, requisitos="", materias=[])],
    )

    chunks_returned = [edital_chunk1, edital_chunk2]
    call_index = 0

    async def side_effect(chunk):
        nonlocal call_index
        result = chunks_returned[min(call_index, len(chunks_returned) - 1)]
        call_index += 1
        return result

    with patch.object(service, '_extract_from_chunk', side_effect=side_effect), \
         patch.object(service, '_create_edital_db', new_callable=AsyncMock,
                      return_value=None), \
         patch.object(service, '_persist_and_broadcast', new_callable=AsyncMock):

        result = await service.extract_edital_data(md_content=large_content)
        titles = [c.titulo for c in result.cargos]
        assert "Analista" in titles
        assert "Técnico" in titles


# ── _extract_from_chunk — unexpected exception path ──────────────────────────

@pytest.mark.asyncio
async def test_extract_from_chunk_unexpected_exception_continues(monkeypatch):
    monkeypatch.setattr("app.services.ai_service.settings.groq_api_key", None)
    monkeypatch.setattr("app.services.ai_service.settings.nvidia_api_key", None)
    monkeypatch.setattr("app.services.ai_service.settings.openrouter_api_key", None)
    monkeypatch.setattr("app.services.ai_service.settings.gemini_api_key", None)
    service = AIService()

    with patch.object(service.ollama_provider, 'generate_json',
                      new_callable=AsyncMock,
                      side_effect=RuntimeError("unexpected")):
        result = await service._extract_from_chunk("test chunk")
        assert result is None
