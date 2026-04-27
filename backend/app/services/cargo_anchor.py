import re
import logging
from pathlib import Path
from typing import List, Dict, Optional

logger = logging.getLogger(__name__)

class AnchorEngine:
    """
    Camada 2 da Montanha: Tecnologia de Ancoragem de Cargos.
    Localiza a 'janela de texto' exata no main.md para cada CargoSeed.
    """

    def __init__(self):
        # Regex para capturar headers Markdown (#, ##, ###, ####, #####, ######)
        self.header_re = re.compile(r"^(#+)\s+(.+)$", re.MULTILINE)

    def anchor(self, main_md: str, titles: List[str], storage_path: Optional[Path] = None) -> Dict[str, str]:
        """
        Recebe o texto completo do main.md e uma lista de títulos de cargos.
        Retorna um dicionário {titulo: recorte_de_texto}.
        """
        headers = []
        for match in self.header_re.finditer(main_md):
            headers.append({
                "level": len(match.group(1)),
                "text": match.group(2).strip(),
                "start": match.start(),
                "end": match.end()
            })

        results = {}
        for title in titles:
            # Encontrar todas as seções relevantes para este cargo via Headers
            sections = self._find_all_relevant_sections(main_md, headers, title)
            if sections:
                results[title] = "\n\n---\n\n".join(sections)
            elif storage_path:
                # Fallback: Se não ancorou via Header, busca em tabelas (Caso IBFC/Quadrix)
                logger.info(f"AnchorEngine: Header fallback para '{title}'. Buscando em tabelas...")
                table_ctx = self._fallback_to_tables(storage_path, title)
                if table_ctx:
                    results[title] = table_ctx
        
        return results

    def _fallback_to_tables(self, storage_path: Path, title: str) -> Optional[str]:
        """Busca o cargo dentro dos arquivos de tabela e retorna o fragmento como contexto."""
        # Tenta data.md primeiro (Trindade)
        data_md = storage_path / "data.md"
        if data_md.exists():
            content = data_md.read_text(encoding="utf-8")
            # Procura a linha que contém o cargo. 
            # Como data.md é focado em tabelas, pegamos um bloco de contexto ao redor da menção
            lines = content.splitlines()
            for i, line in enumerate(lines):
                if title.lower() in line.lower():
                    # Pega 5 linhas antes e 5 depois para garantir o contexto da tabela
                    start = max(0, i - 5)
                    end = min(len(lines), i + 10)
                    return "\n".join(lines[start:end])

        # Fallback secundário: percorre diretório tables/
        tables_dir = storage_path / "tables"
        if tables_dir.exists():
            for tf in tables_dir.glob("*.md"):
                content = tf.read_text(encoding="utf-8")
                if title.lower() in content.lower():
                    return content
        
        return None

    def _find_all_relevant_sections(self, main_md: str, headers: List[Dict], title: str) -> List[str]:
        relevant_sections = []
        
        # Normalizar título para busca
        title_norm = title.lower().strip()
        keywords = [w.lower() for w in re.split(r"[\s/\(\)\-–]+", title) if len(w) > 3]

        for i, h in enumerate(headers):
            h_text_norm = h["text"].lower().strip()
            is_relevant = False

            # 1. Busca exata
            if h_text_norm == title_norm:
                is_relevant = True
            
            # 2. Busca parcial (título contido no header)
            elif title_norm in h_text_norm:
                is_relevant = True
            
            # 3. Busca parcial (header contido no título - ex: "Técnico" em "Técnico do Seguro Social")
            # Mas cuidado para não pegar "Agente" em "Agente de Limpeza" e "Agente de Segurança"
            # Então exigimos que o header tenha um tamanho mínimo se for substring
            elif len(h_text_norm) > 10 and h_text_norm in title_norm:
                is_relevant = True

            # 4. Busca por palavras-chave (se o header contém todas as palavras principais do cargo)
            elif keywords and all(kw in h_text_norm for kw in keywords):
                is_relevant = True

            if is_relevant:
                start_pos = h["start"]
                current_level = h["level"]
                
                # O fim da seção é o próximo header de nível igual ou superior (menor número de #)
                end_pos = len(main_md)
                for j in range(i + 1, len(headers)):
                    if headers[j]["level"] <= current_level:
                        end_pos = headers[j]["start"]
                        break
                
                section_content = main_md[start_pos:end_pos].strip()
                if section_content:
                    relevant_sections.append(section_content)

        return relevant_sections

    def get_context_for_cargo(self, content_hash: str, title: str) -> Optional[str]:
        """Helper para carregar o main.md e ancorar um único cargo."""
        storage_path = Path("backend/storage/processed") / content_hash
        if not storage_path.exists():
            storage_path = Path("storage/processed") / content_hash
        
        main_md_path = storage_path / "main.md"
        if not main_md_path.exists():
            return None
            
        main_md = main_md_path.read_text(encoding="utf-8")
        results = self.anchor(main_md, [title])
        return results.get(title)
