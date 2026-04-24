import asyncio
import logging
from typing import List, Optional, Set

from app.core.config import settings
from app.core.logging_streamer import log_streamer
from app.db import models as db_models
from app.db.database import SessionLocal
from app.providers.base_provider import BaseLLMProvider
from app.providers.gemini_provider import GeminiProvider
from app.providers.ollama_provider import OllamaProvider
from app.providers.groq_provider import GroqProvider
from app.providers.openrouter_provider import OpenRouterProvider
from app.providers.nvidia_provider import NVIDIAProvider
from app.schemas.edital_schema import Cargo, EditalGeral, EditalResponse, Materia, StatusEdital
from app.services.chunker_service import MarkdownChunker

logger = logging.getLogger(__name__)

CHUNK_THRESHOLD = 15_000
CHUNK_SIZE = 15_000
CHUNK_OVERLAP = 1_000


class AIService:
    """Orquestra seleção de provider LLM, estratégia de failover e persistência incremental."""

    def __init__(self) -> None:
        self.ollama_provider = OllamaProvider()
        self.gemini_provider = GeminiProvider()
        self.groq_provider = GroqProvider()
        self.openrouter_provider = OpenRouterProvider()
        self.nvidia_provider = NVIDIAProvider()
        
        self.strategy = settings.llm_strategy
        self.cloud_fallback = settings.cloud_fallback
        logger.info(f"AIService initialized with strategy={self.strategy}, cloud_fallback={self.cloud_fallback}")

    # ------------------------------------------------------------------ #
    #  Provider chain                                                       #
    # ------------------------------------------------------------------ #

    def _get_provider_chain(self) -> List[BaseLLMProvider]:
        """Constrói lista ordenada de providers conforme a estratégia configurada e chaves disponíveis.

        Ordem: Ollama -> Groq -> Gemini -> NVIDIA -> OpenRouter
        """
        if self.strategy == "local_only":
            return [self.ollama_provider]
        
        chain: List[BaseLLMProvider] = []

        # 1. Ollama (Sempre tenta se local_first)
        if self.strategy == "local_first" or self.strategy == "hybrid":
            chain.append(self.ollama_provider)

        # 2. Groq (Velocidade)
        if settings.groq_api_key:
            chain.append(self.groq_provider)

        # 3. Gemini (Contexto/Cloud padrão)
        if settings.gemini_api_key:
            chain.append(self.gemini_provider)

        # 4. NVIDIA (Qualidade/Pesado)
        if settings.nvidia_api_key:
            chain.append(self.nvidia_provider)

        # 5. OpenRouter (Fallback final)
        if settings.openrouter_api_key:
            chain.append(self.openrouter_provider)

        if not chain:
            logger.error("Nenhum provider LLM configurado corretamente (chaves ausentes).")
            # Adiciona Ollama como último recurso mesmo sem configuração explícita
            chain.append(self.ollama_provider)

        return chain

    # ------------------------------------------------------------------ #
    #  LLM extraction                                                       #
    # ------------------------------------------------------------------ #

    async def _extract_from_chunk(self, chunk: str) -> Optional[EditalGeral]:
        """Executa a cadeia de failover de providers em um único chunk.

        Args:
            chunk: Fragmento de markdown a ser processado pela IA.

        Returns:
            EditalGeral extraído, ou None se todos os providers falharem.
        """
        prompt = f'''
        Analise o edital abaixo e extraia os dados estruturados.
        Foque especialmente na separação por CARGOS. Cada cargo deve ter suas matérias e requisitos.
        Retorne APENAS o JSON puro seguindo este schema:
        {EditalGeral.model_json_schema()}

        EDITAL EM MARKDOWN:
        {chunk}
        '''

        for provider in self._get_provider_chain():
            try:
                logger.info(f"Tentando provider {provider.__class__.__name__}...")
                log_streamer.broadcast({"type": "log", "message": f"🤖 IA: Tentando extração com {provider.__class__.__name__}...", "level": "INFO"})
                result: EditalGeral = await provider.generate_json(prompt=prompt, schema=EditalGeral)
                logger.info(f"Provider {provider.__class__.__name__} respondeu com sucesso.")
                return result
            except (ConnectionError, TimeoutError, ValueError) as e:
                logger.error(f"❌ {provider.__class__.__name__} falhou na extração: {str(e)}")
                # Broadcast the specific error to Cockpit
                log_streamer.broadcast({
                    "type": "log", 
                    "message": f"⚠️ {provider.__class__.__name__}: {str(e)}", 
                    "level": "WARNING"
                })
                continue
            except Exception as e:
                logger.error(f"{provider.__class__.__name__} erro inesperado: {e}")
                log_streamer.broadcast({"type": "log", "message": f"⚠️ {provider.__class__.__name__} falhou, tentando próximo...", "level": "WARNING"})

        return None

    # ------------------------------------------------------------------ #
    #  Pydantic-level merge helpers                                         #
    # ------------------------------------------------------------------ #

    @staticmethod
    def _merge_materias(existing: List[Materia], incoming: List[Materia]) -> List[Materia]:
        """Mescla duas listas de matérias, deduplicando por nome.

        Args:
            existing: Matérias já acumuladas.
            incoming: Novas matérias a incorporar.

        Returns:
            Lista unificada sem duplicatas de nome.
        """
        seen = {m.nome: m for m in existing}
        for m in incoming:
            if m.nome not in seen:
                seen[m.nome] = m
        return list(seen.values())

    @staticmethod
    def _merge_cargos(base: List[Cargo], incoming: List[Cargo]) -> List[Cargo]:
        """Acumula cargos; mescla matérias para cargos com mesmo título.

        Args:
            base: Cargos já consolidados.
            incoming: Novos cargos extraídos do chunk atual.

        Returns:
            Lista consolidada de cargos sem duplicatas de título.
        """
        index = {c.titulo: c for c in base}
        for cargo in incoming:
            if cargo.titulo in index:
                merged = AIService._merge_materias(index[cargo.titulo].materias, cargo.materias)
                index[cargo.titulo] = index[cargo.titulo].model_copy(update={"materias": merged})
            else:
                index[cargo.titulo] = cargo
        return list(index.values())

    # ------------------------------------------------------------------ #
    #  Database persistence (sync, runs in thread via asyncio.to_thread)   #
    # ------------------------------------------------------------------ #

    @staticmethod
    def _create_edital_sync(result: EditalGeral) -> Optional[int]:
        """Cria o registro Edital no banco de dados.

        Args:
            result: EditalGeral com os metadados globais do edital.

        Returns:
            ID do Edital criado, ou None se a operação falhar.
        """
        db = SessionLocal()
        try:
            edital_db = db_models.Edital(
                orgao=result.orgao,
                banca=result.banca,
                data_prova=result.data_prova,
                link=result.link_edital,
                status=StatusEdital.INGESTADO,
            )
            db.add(edital_db)
            db.commit()
            db.refresh(edital_db)
            logger.info(f"Edital '{result.orgao}' criado no banco (id={edital_db.id}).")
            return edital_db.id
        except Exception as e:
            logger.error(f"Falha ao criar Edital no banco: {e}")
            db.rollback()
            return None
        finally:
            db.close()

    @staticmethod
    def _persist_cargos_sync(
        edital_db_id: int,
        cargos: List[Cargo],
        known_titulos: Set[str],
    ) -> List[dict]:
        """Persiste cargos novos de um chunk no banco de dados.

        Cargos cujo título já consta em known_titulos são ignorados (já salvos).
        Mutates known_titulos in-place com os títulos recém-persistidos.

        Args:
            edital_db_id: ID do Edital pai no banco.
            cargos: Lista de cargos Pydantic do chunk atual.
            known_titulos: Conjunto de títulos já persistidos (mutado in-place).

        Returns:
            Lista de dicts dos cargos efetivamente salvos (para broadcast posterior).
        """
        saved: List[dict] = []
        db = SessionLocal()
        try:
            for cargo_schema in cargos:
                if cargo_schema.titulo in known_titulos:
                    continue

                cargo_db = db_models.Cargo(
                    edital_id=edital_db_id,
                    titulo=cargo_schema.titulo,
                    salario=cargo_schema.salario,
                    requisitos=cargo_schema.requisitos,
                    status="extraido",
                    price=0.0,
                )
                db.add(cargo_db)
                db.flush()

                for materia_schema in cargo_schema.materias:
                    materia_db = db_models.Materia(
                        cargo_id=cargo_db.id,
                        nome=materia_schema.nome,
                    )
                    db.add(materia_db)
                    db.flush()

                    for topico_str in materia_schema.topicos:
                        db.add(db_models.Topico(
                            materia_id=materia_db.id,
                            conteudo=topico_str,
                        ))

                db.commit()
                known_titulos.add(cargo_schema.titulo)
                saved.append(cargo_schema.model_dump())

        except Exception as e:
            logger.error(f"Falha ao persistir cargos no banco (edital_id={edital_db_id}): {e}")
            db.rollback()
        finally:
            db.close()

        return saved

    # ------------------------------------------------------------------ #
    #  Async wrappers                                                        #
    # ------------------------------------------------------------------ #

    async def _create_edital_db(self, result: EditalGeral) -> Optional[int]:
        return await asyncio.to_thread(self._create_edital_sync, result)

    async def _persist_and_broadcast(
        self,
        edital_db_id: int,
        cargos: List[Cargo],
        known_titulos: Set[str],
    ) -> None:
        """Persiste cargos em thread e faz broadcast dos salvos no event loop.

        Args:
            edital_db_id: ID do Edital pai.
            cargos: Cargos Pydantic a persistir.
            known_titulos: Títulos já persistidos (mutado in-place).
        """
        saved = await asyncio.to_thread(
            self._persist_cargos_sync, edital_db_id, cargos, known_titulos
        )
        for cargo_dict in saved:
            logger.info(f"Cargo '{cargo_dict['titulo']}' extraído e salvo!")
            log_streamer.broadcast({"type": "data", "payload": cargo_dict})

    # ------------------------------------------------------------------ #
    #  Public entry point                                                    #
    # ------------------------------------------------------------------ #

    async def extract_edital_data(self, md_content: str) -> EditalResponse:
        """Extrai dados estruturados de um edital em markdown com persistência incremental.

        Para conteúdos <= CHUNK_THRESHOLD: single-pass.
        Para conteúdos maiores: divide em chunks sobrepostos, processa sequencialmente,
        persiste cargos após cada chunk e mescla resultados.

        Args:
            md_content: Conteúdo do edital convertido para markdown.

        Returns:
            EditalGeral consolidado com todos os cargos encontrados.

        Raises:
            RuntimeError: Se nenhum cargo for extraído após todas as tentativas.
        """
        # ── Single-pass ──────────────────────────────────────────────────
        if (len(md_content) <= CHUNK_THRESHOLD):
            logger.info(f"Edital pequeno ({len(md_content)} chars) — processamento direto.")
            logger.debug(f"Markdown Content (First 500 chars): {md_content[:500]}...")
            result = await self._extract_from_chunk(md_content)
            if result is None:
                raise RuntimeError("Todos os providers LLM falharam na extração.")

            edital_db_id = await self._create_edital_db(result)
            if edital_db_id:
                await self._persist_and_broadcast(edital_db_id, result.cargos, set())

            return EditalResponse(
                **result.model_dump(),
                id=edital_db_id,
                status=StatusEdital.INGESTADO,
            )

        # ── Chunked ──────────────────────────────────────────────────────
        chunker = MarkdownChunker(chunk_size=CHUNK_SIZE, overlap=CHUNK_OVERLAP)
        chunks = chunker.split(md_content)
        total = len(chunks)
        logger.info(f"Edital grande ({len(md_content)} chars) dividido em {total} chunks.")

        merged: Optional[EditalGeral] = None
        edital_db_id: Optional[int] = None
        known_titulos: Set[str] = set()
        failed_chunks: List[int] = []

        for idx, chunk in enumerate(chunks, start=1):
            logger.info(f"Processando chunk {idx}/{total} ({len(chunk)} chars)...")
            result = await self._extract_from_chunk(chunk)
            await asyncio.sleep(2.0)

            if result is None:
                logger.warning(f"Chunk {idx}/{total} falhou — pulando.")
                failed_chunks.append(idx)
                continue

            if merged is None:
                # First successful chunk: seed metadata + create DB edital
                merged = result
                logger.info(f"Chunk {idx}: metadados globais capturados, {len(result.cargos)} cargo(s).")
                edital_db_id = await self._create_edital_db(result)
                if edital_db_id:
                    await self._persist_and_broadcast(edital_db_id, result.cargos, known_titulos)
            else:
                # Subsequent chunks: merge cargos + persist only new ones
                new_cargos = [c for c in result.cargos if c.titulo not in known_titulos]
                if edital_db_id and new_cargos:
                    await self._persist_and_broadcast(edital_db_id, new_cargos, known_titulos)

                merged_cargos = self._merge_cargos(merged.cargos, result.cargos)
                merged = merged.model_copy(update={"cargos": merged_cargos})
                logger.info(
                    f"Chunk {idx}/{total}: {len(result.cargos)} cargo(s) processados, "
                    f"total consolidado={len(merged.cargos)}."
                )

        if merged is None or not merged.cargos:
            raise RuntimeError(
                f"Extração em chunks não produziu cargos. "
                f"Chunks falhos: {failed_chunks}/{total}"
            )

        if failed_chunks:
            logger.warning(f"Extração concluída com {len(failed_chunks)} chunk(s) falho(s): {failed_chunks}")

        logger.info(f"EditalGeral consolidado — {len(merged.cargos)} cargo(s) no total.")
        return EditalResponse(
            **merged.model_dump(),
            id=edital_db_id,
            status=StatusEdital.INGESTADO,
        )
