import pymupdf4llm
import logging

logger = logging.getLogger(__name__)

class PDFService:
    @staticmethod
    def to_markdown(file_path: str) -> str:
        """Converte um arquivo PDF para Markdown preservando tabelas e estrutura.

        Args:
            file_path: Caminho absoluto ou relativo para o arquivo PDF.

        Returns:
            Conteúdo do PDF convertido para Markdown.

        Raises:
            RuntimeError: Se o pymupdf4llm falhar ao processar o arquivo.
        """
        try:
            logger.info(f"PDFService: Convertendo {file_path}")
            md_text: str = pymupdf4llm.to_markdown(file_path)
            return md_text
        except Exception as e:
            logger.error(f"PDFService: Falha na conversão de '{file_path}' - {e}")
            raise RuntimeError(f"Falha ao extrair texto do PDF '{file_path}': {e}") from e
