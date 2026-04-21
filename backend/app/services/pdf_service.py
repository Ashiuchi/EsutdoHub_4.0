import pymupdf4llm
import logging

logger = logging.getLogger(__name__)

class PDFService:
    @staticmethod
    def to_markdown(file_path: str) -> str:
        """
        Converte um arquivo PDF para Markdown preservando tabelas e estrutura.
        """
        try:
            logger.info(f"PDFService: Convertendo {file_path}")
            md_text = pymupdf4llm.to_markdown(file_path)
            return md_text
        except Exception as e:
            logger.error(f"PDFService: Falha na conversão - {e}")
            raise Exception(f'Erro na extração de texto do PDF: {str(e)}')
