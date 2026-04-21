import pytest
import logging
import os
from app.services.ai_service import AIService

logger = logging.getLogger(__name__)


@pytest.mark.asyncio
@pytest.mark.integration
async def test_extract_edital_from_markdown():
    """E2E test: Extract edital from markdown using local Llama 3 via Ollama"""
    # Note: This test requires:
    # 1. Ollama running locally at http://localhost:11434
    # 2. llama3.1:8b model downloaded (ollama pull llama3.1:8b)
    # 3. LLM_STRATEGY=local_first in environment

    service = AIService()

    # Read sample markdown content (simulating PDF extraction)
    fixture_path = os.path.join(
        os.path.dirname(__file__),
        "../fixtures/trt_sample.md"
    )

    with open(fixture_path, "r", encoding="utf-8") as f:
        md_content = f.read()

    logger.info("Starting E2E edital extraction with local Llama 3")
    logger.info(f"Using strategy: {service.strategy}")

    result = await service.extract_edital_data(md_content=md_content)

    # Assertions - verify all required fields extracted
    assert result.orgao is not None, "Orgao (organization) should be extracted"
    assert len(result.orgao) > 0, "Orgao should not be empty"

    assert result.banca is not None, "Banca (exam board) should be extracted"
    assert len(result.banca) > 0, "Banca should not be empty"

    assert len(result.cargos) > 0, "At least one cargo (position) should be extracted"

    # Verify each cargo has required fields
    for i, cargo in enumerate(result.cargos):
        assert cargo.titulo, f"Cargo {i} titulo should not be empty"
        assert cargo.vagas_ampla >= 0, f"Cargo {i} vagas_ampla should be non-negative"
        assert cargo.salario >= 0, f"Cargo {i} salario should be non-negative"
        assert len(cargo.materias) > 0, f"Cargo {i} should have at least one materia"

        # Verify each materia has required fields
        for j, materia in enumerate(cargo.materias):
            assert materia.nome, f"Cargo {i} Materia {j} nome should not be empty"
            assert len(materia.topicos) > 0, f"Cargo {i} Materia {j} should have at least one topico"

    logger.info(f"✓ Successfully extracted edital with {len(result.cargos)} cargos")
    logger.info(f"  Extracted organization: {result.orgao}")
    logger.info(f"  Exam board: {result.banca}")
    logger.info(f"  Cargos extracted: {[c.titulo for c in result.cargos]}")

    # Print summary for verification
    print(f"\n{'='*60}")
    print(f"E2E TEST RESULT SUMMARY")
    print(f"{'='*60}")
    print(f"Organization: {result.orgao}")
    print(f"Exam Board: {result.banca}")
    print(f"Total Positions: {len(result.cargos)}")
    for cargo in result.cargos:
        print(f"\n  Position: {cargo.titulo}")
        print(f"    - Vagas (Ampla): {cargo.vagas_ampla}")
        print(f"    - Vagas (Cotas): {cargo.vagas_cotas}")
        print(f"    - Salary: R$ {cargo.salario:,.2f}")
        print(f"    - Subjects: {len(cargo.materias)}")
        for materia in cargo.materias:
            print(f"      • {materia.nome}: {materia.topicos}")
    print(f"{'='*60}\n")
