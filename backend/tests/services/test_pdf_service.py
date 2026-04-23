import pytest
from unittest.mock import patch
from app.services.pdf_service import PDFService


def test_to_markdown_success():
    with patch('pymupdf4llm.to_markdown', return_value="# Conteúdo\nTexto extraído.") as mock:
        result = PDFService.to_markdown("edital.pdf")
        assert result == "# Conteúdo\nTexto extraído."
        mock.assert_called_once_with("edital.pdf")


def test_to_markdown_raises_runtime_error_on_failure():
    with patch('pymupdf4llm.to_markdown', side_effect=Exception("file corrupted")):
        with pytest.raises(RuntimeError, match="Falha ao extrair texto do PDF"):
            PDFService.to_markdown("corrupted.pdf")


def test_to_markdown_wraps_file_not_found():
    with patch('pymupdf4llm.to_markdown', side_effect=FileNotFoundError("no file")):
        with pytest.raises(RuntimeError) as exc_info:
            PDFService.to_markdown("missing.pdf")
        assert "missing.pdf" in str(exc_info.value)


def test_to_markdown_preserves_original_cause():
    original = ValueError("bad pdf")
    with patch('pymupdf4llm.to_markdown', side_effect=original):
        with pytest.raises(RuntimeError) as exc_info:
            PDFService.to_markdown("bad.pdf")
        assert exc_info.value.__cause__ is original
