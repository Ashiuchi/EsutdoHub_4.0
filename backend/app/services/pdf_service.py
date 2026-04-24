import logging

from app.services.geometric_engine import GeometricEngine

logger = logging.getLogger(__name__)


class PDFService:
    @staticmethod
    def to_markdown(file_path: str) -> str:
        logger.info("Starting PDF conversion: file=%s", file_path)
        try:
            md_text = GeometricEngine().document_to_markdown(file_path)
            logger.info("GeometricEngine extraction succeeded: %d chars", len(md_text))
            return md_text
        except Exception as e:
            raise RuntimeError(f"Falha ao extrair texto do PDF: {file_path}") from e
