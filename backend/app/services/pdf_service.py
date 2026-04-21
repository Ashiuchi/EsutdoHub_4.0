import pymupdf4llm
import os

class PDFService:
    @staticmethod
    def to_markdown(file_path: str) -> str:
        try:
            # Converte o PDF para Markdown preservando a estrutura de tabelas
            md_text = pymupdf4llm.to_markdown(file_path)
            return md_text
        except Exception as e:
            raise Exception(f'Erro na conversão do PDF: {str(e)}')
