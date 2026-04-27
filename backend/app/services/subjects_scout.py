import re
import logging
import asyncio
from pathlib import Path
from typing import List, Dict
from pydantic import BaseModel

from app.providers.base_provider import BaseLLMProvider
from app.schemas.edital_schema import Cargo, Materia
from app.core.logging_streamer import log_streamer

logger = logging.getLogger(__name__)

# Ollama/Groq: prompt enxuto, contexto pequeno
_PROMPT_LITE = """Analise o fragmento de edital e extraia o conteúdo programático para o cargo "{titulo}".

Responda SOMENTE com JSON válido, sem texto adicional:
{{"materias": [{{"nome": "nome da matéria", "topicos": ["tópico 1", "tópico 2"]}}]}}

Se não encontrar conteúdo programático para o cargo, retorne: {{"materias": []}}

FRAGMENTO DO EDITAL:
{context}
"""

# Gemini Pro: prompt rico, contexto grande
_PROMPT_ELITE = """Você é um especialista em análise de editais de concurso público brasileiro.

Analise o trecho abaixo e extraia o programa COMPLETO de estudos para o cargo "{titulo}".

REGRAS:
1. Liste todas as matérias/disciplinas exigidas para o cargo.
2. Para cada matéria, extraia todos os tópicos de forma granular.
3. Responda APENAS com JSON válido seguindo o schema abaixo.

SCHEMA:
{{"materias": [{{"nome": "string", "topicos": ["string", "string"], "peso": null, "quantidade_questoes": null}}]}}

EDITAL:
{context}
"""

# Tabular fallback: used when the programmatic section is entirely in tables
_PROMPT_TABLE = """Analise o conteúdo abaixo e extraia as matérias e tópicos para o cargo "{titulo}".

O conteúdo abaixo pode estar em formato de tabela. Extraia as matérias e tópicos ignorando a estrutura de colunas e focando no texto.

Responda SOMENTE com JSON válido, sem texto adicional:
{{"materias": [{{"nome": "nome da matéria", "topicos": ["tópico 1", "tópico 2"]}}]}}

Se não encontrar conteúdo programático para o cargo, retorne: {{"materias": []}}

CONTEÚDO:
{context}
"""

_LITE_PROVIDERS = {"OllamaProvider", "GroqProvider", "OpenRouterProvider"}
_ELITE_CONTEXT_LIMIT = 20_000
_LITE_CONTEXT_LIMIT = 2_000  # Reduzido para 2k para modelos 3b
_CHUNK_OVERLAP = 200


class CargoSubjects(BaseModel):
    materias: List[Materia]


class SubjectsScoutAgent:
    def __init__(self):
        self.semaphore = asyncio.Semaphore(2)

    async def scout(self, content_hash: str, cargos: List[Cargo], chain: List[BaseLLMProvider], cargo_contexts: dict = None) -> List[Cargo]:
        """Extrai o conteúdo programático (Matérias→Tópicos) para cada cargo."""
        storage_path = Path("backend/storage/processed") / content_hash
        if not storage_path.exists():
            storage_path = Path("storage/processed") / content_hash
        if not storage_path.exists():
            logger.error(f"Storage não encontrado para {content_hash}")
            return cargos

        source_file = storage_path / "clean.md"
        if not source_file.exists():
            source_file = storage_path / "main.md"
            
        text_source = source_file.read_text(encoding="utf-8") if source_file.exists() else ""
        table_files = sorted((storage_path / "tables").glob("*.md")) if (storage_path / "tables").exists() else []

        log_streamer.broadcast({"type": "log", "message": "📚 Iniciando Subjects Scout (Mestre de Conteúdo)...", "level": "INFO"})

        global_content_section = self._find_subjects_section(text_source)
        using_table_fallback = False
        if not global_content_section:
            if table_files:
                log_streamer.broadcast({"type": "log", "message": "⚠️ Seção programática não detectada — usando fallback tabular (todas as tabelas).", "level": "WARNING"})
                global_content_section = self._build_table_fallback_context(table_files)
                using_table_fallback = True
            else:
                log_streamer.broadcast({"type": "log", "message": "⚠️ Seção de Conteúdo Programático não detectada — usando início do documento.", "level": "WARNING"})
                global_content_section = text_source[:30_000]

        tasks = []
        for cargo in cargos:
            anchor_ctx = cargo_contexts.get(cargo.titulo) if cargo_contexts else None
            section = anchor_ctx if anchor_ctx else global_content_section
            is_tabular = using_table_fallback and not bool(anchor_ctx)
            tasks.append(self._extract_for_cargo(cargo, section, table_files, chain, is_anchored=bool(anchor_ctx), is_tabular=is_tabular))
            
        results = await asyncio.gather(*tasks)

        updated = []
        for cargo, materias in zip(cargos, results):
            cargo.materias = materias
            updated.append(cargo)
            if materias:
                log_streamer.broadcast({
                    "type": "log",
                    "message": f"📚 {cargo.titulo}: {len(materias)} matérias extraídas.",
                    "level": "INFO",
                })
        return updated

    def _build_table_fallback_context(self, table_files: List[Path], limit: int = 30_000) -> str:
        """Concatenate all table files as fallback context for 100% tabular editais."""
        parts = []
        total = 0
        for tf in table_files:
            content = tf.read_text(encoding="utf-8")
            parts.append(content)
            total += len(content)
            if total >= limit:
                break
        return "\n\n".join(parts)[:limit]

    def _find_subjects_section(self, text: str) -> str:
        patterns = [
            r"CONTEÚDO PROGRAMÁTICO",
            r"DOS CONTEÚDOS PROGRAMÁTICOS",
            r"ANEXO\s+[IVX]+.*?CONTEÚDO",
            r"PROVAS OBJETIVAS.*?CONHECIMENTOS",
            r"PROGRAMA DE PROVAS",
        ]
        for p in patterns:
            m = re.search(p, text, re.IGNORECASE | re.DOTALL)
            if m:
                return text[m.start(): m.start() + 60_000]
        return ""

    def _find_cargo_subsection(self, section: str, titulo: str, limit: int) -> str:
        keywords = [w for w in re.split(r"[\s/\(\)]+", titulo) if len(w) > 3]
        best = -1
        for kw in keywords:
            pos = section.lower().find(kw.lower())
            if pos != -1:
                best = pos
                break
        start = max(0, best - 300) if best != -1 else 0
        return section[start: start + limit]

    def _get_relevant_tables(self, table_files: List[Path], titulo: str, limit: int = 2000) -> str:
        keywords = [w for w in re.split(r"[\s/\(\)]+", titulo) if len(w) > 3]
        snippets = []
        total = 0
        for tf in table_files:
            content = tf.read_text(encoding="utf-8")
            if any(kw.lower() in content.lower() for kw in keywords):
                chunk = content[:500]
                snippets.append(chunk)
                total += len(chunk)
                if total >= limit:
                    break
        return "\n\n".join(snippets)

    def _merge_materias(self, base: List[Materia], incoming: List[Materia]) -> List[Materia]:
        """Mescla matérias e tópicos de múltiplos chunks sem duplicar."""
        index = {self._normalize(m.nome): m for m in base}
        for m in incoming:
            key = self._normalize(m.nome)
            if key in index:
                existing_topics = set(index[key].topicos)
                for t in m.topicos:
                    if t not in existing_topics:
                        index[key].topicos.append(t)
            else:
                index[key] = m
        return list(index.values())

    @staticmethod
    def _normalize(name: str) -> str:
        return re.sub(r"[^a-z0-9]", "", name.lower())

    async def _extract_for_cargo(
        self,
        cargo: Cargo,
        section: str,
        table_files: List[Path],
        chain: List[BaseLLMProvider],
        is_anchored: bool = False,
        is_tabular: bool = False,
    ) -> List[Materia]:
        async with self.semaphore:
            table_ctx = self._get_relevant_tables(table_files, cargo.titulo)

            for provider in chain:
                provider_name = provider.__class__.__name__
                is_elite = provider_name not in _LITE_PROVIDERS
                ctx_limit = _ELITE_CONTEXT_LIMIT if is_elite else _LITE_CONTEXT_LIMIT
                if is_tabular:
                    template = _PROMPT_TABLE
                else:
                    template = _PROMPT_ELITE if is_elite else _PROMPT_LITE

                # Determinar o contexto base (seção ancorada ou heurística)
                if is_anchored:
                    base_context = section
                else:
                    base_context = self._find_cargo_subsection(section, cargo.titulo, 10_000) # Busca num range maior antes de fatiar

                # Se for Ollama, aplicamos o fatiamento (Chunking Interno)
                if provider_name == "OllamaProvider" and len(base_context) > ctx_limit:
                    logger.info(f"Ollama fatiando contexto para '{cargo.titulo}' ({len(base_context)} chars)")
                    all_materias = []
                    
                    # Fatiamento com overlap
                    i = 0
                    while i < len(base_context):
                        chunk = base_context[i : i + ctx_limit]
                        context = (chunk + ("\n\n---\nTABELAS RELEVANTES:\n" + table_ctx if table_ctx else "")).strip()
                        prompt = template.format(titulo=cargo.titulo, context=context)
                        
                        try:
                            result: CargoSubjects = await provider.generate_json(prompt=prompt, schema=CargoSubjects)
                            if result.materias:
                                all_materias = self._merge_materias(all_materias, result.materias)
                        except Exception as e:
                            logger.warning(f"Ollama chunk {i} falhou: {e}")
                        
                        i += (ctx_limit - _CHUNK_OVERLAP)
                    
                    if all_materias:
                        return all_materias
                else:
                    # Fluxo normal para outros providers ou contextos pequenos
                    context = (base_context[:ctx_limit] + ("\n\n---\nTABELAS RELEVANTES:\n" + table_ctx if table_ctx else "")).strip()
                    prompt = template.format(titulo=cargo.titulo, context=context)
                    try:
                        result: CargoSubjects = await provider.generate_json(prompt=prompt, schema=CargoSubjects)
                        if result.materias:
                            logger.info(f"✓ {provider_name} extraiu {len(result.materias)} matérias para '{cargo.titulo}'")
                            return result.materias
                    except Exception as e:
                        logger.warning(f"⚠️ {provider_name} falhou: {e}")

            logger.error(f"Todos os providers falharam para '{cargo.titulo}'.")
            return []
