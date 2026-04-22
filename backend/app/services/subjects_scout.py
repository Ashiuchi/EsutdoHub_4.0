import os
import re
import logging
import asyncio
from pathlib import Path
from typing import List, Dict, Any, Optional
from pydantic import BaseModel

from app.providers.ollama_provider import OllamaProvider
from app.providers.gemini_provider import GeminiProvider
from app.core.config import settings
from app.schemas.edital_schema import Cargo, Materia
from app.core.logging_streamer import log_streamer

logger = logging.getLogger(__name__)

class CargoSubjects(BaseModel):
    titulo_cargo: str
    materias: List[Materia]

class SubjectsScoutAgent:
    def __init__(self):
        self.ollama_provider = OllamaProvider(timeout=600)
        self.gemini_provider = GeminiProvider()
        self.semaphore = asyncio.Semaphore(2)  # Extração de tópicos é densa, limitamos mais

    async def scout(self, content_hash: str, cargos: List[Cargo]) -> List[Cargo]:
        """Localiza e extrai o conteúdo programático para cada cargo."""
        storage_path = Path("backend/storage/processed") / content_hash
        if not storage_path.exists():
            storage_path = Path("storage/processed") / content_hash
            
        if not storage_path.exists():
            logger.error(f"Storage não encontrado para {content_hash}")
            return cargos

        main_md = (storage_path / "main.md").read_text(encoding="utf-8") if (storage_path / "main.md").exists() else ""
        
        log_streamer.broadcast({"type": "log", "message": "🔍 Iniciando Subjects Scout (Minerador de Conteúdo)...", "level": "INFO"})

        # 1. Localizar Seção de Conteúdo (Heurística)
        content_section = self._find_subjects_section(main_md)
        if not content_section:
            log_streamer.broadcast({"type": "log", "message": "⚠️ Seção de Conteúdo Programático não detectada via heurística.", "level": "WARNING"})
            # Fallback: usar o texto inteiro se for pequeno, ou os primeiros 30k chars
            content_section = main_md[:30000]

        # 2. Processar em lotes para evitar timeout e sobrecarga
        # Mapear Cargos -> Matérias
        updated_cargos = []
        
        tasks = []
        for cargo in cargos:
            tasks.append(self._extract_for_cargo(cargo, content_section))
        
        results = await asyncio.gather(*tasks)
        
        # Merge results
        for cargo, materias in zip(cargos, results):
            cargo.materias = materias
            updated_cargos.append(cargo)
            if materias:
                log_streamer.broadcast({
                    "type": "log", 
                    "message": f"📚 Matérias extraídas para {cargo.titulo}: {len(materias)} disciplinas encontradas.", 
                    "level": "INFO"
                })
        
        return updated_cargos

    def _find_subjects_section(self, text: str) -> str:
        """Tenta encontrar o bloco de texto que contém os conteúdos programáticos."""
        patterns = [
            r"CONTEÚDO PROGRAMÁTICO.*",
            r"DOS CONTEÚDOS PROGRAMÁTICOS.*",
            r"ANEXO [I|V|X]+.*CONTEÚDO.*",
            r"PROVAS OBJETIVAS.*CONHECIMENTOS.*"
        ]
        
        for p in patterns:
            match = re.search(p, text, re.IGNORECASE | re.DOTALL)
            if match:
                # Retorna os próximos 50.000 caracteres a partir do match
                start = match.start()
                return text[start:start+60000]
        return ""

    async def _extract_for_cargo(self, cargo: Cargo, section: str) -> List[Materia]:
        """Usa LLM para extrair matérias e tópicos para um cargo específico."""
        async with self.semaphore:
            prompt = f"""
            Analise o fragmento do edital e extraia o CONTEÚDO PROGRAMÁTICO (Matérias e Tópicos) para o cargo: "{cargo.titulo}".
            
            REGRAS:
            1. Identifique as matérias (ex: Português, Raciocínio Lógico, Conhecimentos Específicos).
            2. Para cada matéria, liste os tópicos de estudo.
            3. Se o edital dividir em "Conhecimentos Básicos" e "Conhecimentos Específicos", extraia ambos.
            4. Ignore pesos e critérios de avaliação, foque apenas nos Tópicos.
            5. Retorne um JSON seguindo o schema CargoSubjects.

            TEXTO:
            {section}
            """
            
            provider = self.ollama_provider if settings.llm_strategy != "cloud_only" else self.gemini_provider
            try:
                result = await provider.generate_json(prompt=prompt, schema=CargoSubjects)
                return result.materias
            except Exception as e:
                logger.error(f"Erro ao extrair matérias para {cargo.titulo}: {e}")
                return []
