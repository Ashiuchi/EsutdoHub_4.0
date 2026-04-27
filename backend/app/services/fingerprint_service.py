import re
import hashlib
import fitz  # PyMuPDF
import unicodedata
import logging

logger = logging.getLogger(__name__)

class FingerprintService:
    @staticmethod
    def normalize_text(text: str) -> str:
        """Remove espaços, pontuação e normaliza caracteres (A-Z, 0-9)."""
        if not text:
            return ""
        # Remove acentos e normaliza para decomposição
        text = "".join(
            c for c in unicodedata.normalize("NFD", text)
            if unicodedata.category(c) != "Mn"
        )
        # Converte para maiúsculas e remove tudo que não for letra ou número
        return re.sub(r"[^A-Z0-9]", "", text.upper())

    @classmethod
    def generate_fingerprint(cls, pdf_bytes: bytes, md_content: str) -> str:
        """
        Gera uma fingerprint heurística baseada em metadados estruturais estáveis.
        """
        try:
            # 1. Paginação (Metadado físico estável)
            doc = fitz.open(stream=pdf_bytes, filetype="pdf")
            page_count = len(doc)
            doc.close()

            # 2. Texto Normalizado (Independente de formatação/espaçamento)
            normalized_md = cls.normalize_text(md_content)
            char_count = len(normalized_md)

            if char_count == 0:
                logger.warning("Empty markdown content for fingerprinting.")
                return f"P:{page_count}|C:0"[:16]

            # 3. Distribuição de Âncoras (%) em texto normalizado
            # As âncoras também devem ser normalizadas para baterem no texto alvo
            anchors = {
                "vagas": r"VAGAS|QUADRODEVAGAS|DASVAGAS",
                "cargos": r"CARGOS|DOSCARGOS",
                "conteudo": r"CONTEUDOPROGRAMATICO|PROGRAMADEPROVAS",
                "provas": r"PROVAS|DASPROVAS"
            }

            positions = []
            for key, pattern in anchors.items():
                match = re.search(pattern, normalized_md)
                if match:
                    # Posição relativa baseada no texto normalizado (super estável)
                    pos = round((match.start() / char_count) * 100, 1)
                    positions.append(str(pos))
                else:
                    positions.append("-1")

            # 4. Composição da Fingerprint
            # Formato: P:Páginas|C:Chars|A:Pos1|Pos2|Pos3|Pos4
            metadata_str = f"P:{page_count}|C:{char_count}|A:{'|'.join(positions)}"
            
            # Hash final (SHA1 encurtado)
            fingerprint = hashlib.sha1(metadata_str.encode()).hexdigest()[:16]
            
            logger.info("Heuristic Fingerprint: %s (meta: %s)", fingerprint, metadata_str)
            return fingerprint

        except Exception as e:
            logger.error("Fingerprint error: %s", e)
            # Fallback para hash básico do conteúdo se tudo falhar
            return hashlib.md5(md_content.encode()).hexdigest()[:16]
