import asyncio
import pytest
from unittest.mock import patch, MagicMock, AsyncMock

from mass_ingestion_industrial import moenda_industrial


@pytest.mark.asyncio
async def test_moenda_skips_pdf_already_in_db(tmp_path):
    """PDFs whose content_hash already exists in DB are skipped without processing."""
    (tmp_path / "edital_teste.pdf").write_bytes(b"%PDF-1.4 fake edital content")

    mock_db = MagicMock()
    mock_db.query.return_value.filter_by.return_value.first.return_value = MagicMock(id="existing")

    async def mock_sleep(seconds):
        if seconds == 300:
            raise KeyboardInterrupt

    with patch("mass_ingestion_industrial.STORAGE_SOURCE", tmp_path), \
         patch("mass_ingestion_industrial.SessionLocal", return_value=mock_db), \
         patch("mass_ingestion_industrial.GeometricEngine") as mock_geo, \
         patch("mass_ingestion_industrial.AIService"), \
         patch("mass_ingestion_industrial.SubtractiveAgent"), \
         patch("mass_ingestion_industrial.FingerprintService"), \
         patch("asyncio.sleep", side_effect=mock_sleep):
        with pytest.raises(KeyboardInterrupt):
            await moenda_industrial()

    mock_geo.return_value.document_to_markdown.assert_not_called()


@pytest.mark.asyncio
async def test_moenda_processes_pdf_not_in_db(tmp_path):
    """PDFs not in DB are processed (GeometricEngine is called)."""
    (tmp_path / "edital_novo.pdf").write_bytes(b"%PDF-1.4 edital novo")

    mock_db = MagicMock()
    mock_db.query.return_value.filter_by.return_value.first.return_value = None

    async def mock_sleep(seconds):
        if seconds == 300:
            raise KeyboardInterrupt

    mock_geo = MagicMock()
    mock_geo.return_value.document_to_markdown.return_value = "# Edital\n"

    mock_ai = MagicMock()
    mock_ai.return_value.process_edital = AsyncMock(return_value={"id": "novo-id"})

    mock_sub = MagicMock()
    mock_sub.return_value.process.return_value = MagicMock(content_hash=None)

    with patch("mass_ingestion_industrial.STORAGE_SOURCE", tmp_path), \
         patch("mass_ingestion_industrial.SessionLocal", return_value=mock_db), \
         patch("mass_ingestion_industrial.GeometricEngine", mock_geo), \
         patch("mass_ingestion_industrial.AIService", mock_ai), \
         patch("mass_ingestion_industrial.SubtractiveAgent", mock_sub), \
         patch("mass_ingestion_industrial.FingerprintService"), \
         patch("asyncio.sleep", side_effect=mock_sleep):
        with pytest.raises(KeyboardInterrupt):
            await moenda_industrial()

    mock_geo.return_value.document_to_markdown.assert_called_once()
