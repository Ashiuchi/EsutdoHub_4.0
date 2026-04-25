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
from app.services.cargo_specialist import CargoTitleAgent
from app.services.cargo_vitaminizer import CargoVitaminizerAgent
from app.services.subjects_scout import SubjectsScoutAgent

logger = logging.getLogger(__name__)

CHUNK_THRESHOLD = 15_000
CHUNK_SIZE = 15_000
CHUNK_OVERLAP = 1_000


class AIService:
    """Orquestra provider chain, pipeline de agentes e persistência incremental."""

    def __init__(self) -> None:
        self.ollama_provider = OllamaProvider()
        self.groq_provider = GroqProvider()
        self.nvidia_provider = NVIDIAProvider()
        self.openrouter_provider = OpenRouterProvider()
        self.gemini_provider = GeminiProvider()

        self.cargo_agent = CargoTitleAgent()
        self.vitaminizer_agent = CargoVitaminizerAgent()
        self.subjects_scout_agent = SubjectsScoutAgent()

        chain_names = [p.__class__.__name__ for p in self._get_provider_chain()]
        logger.info("AIService initialized — chain: %s", " → ".join(chain_names))

    # ------------------------------------------------------------------ #
    #  Provider chain                                                       #
    # ------------------------------------------------------------------ #

    def _get_provider_chain(self) -> List[BaseLLMProvider]:
        """Constrói lista ordenada: Ollama sempre primeiro, cloud providers se tiverem chave."""
        chain: List[BaseLLMProvider] = [self.ollama_provider]

        if settings.groq_api_key:
            chain.append(self.groq_provider)
        if settings.nvidia_api_key:
            chain.append(self.nvidia_provider)
        if settings.openrouter_api_key:
            chain.append(self.openrouter_provider)
        if settings.gemini_api_key:
            chain.append(self.gemini_provider)

        if len(chain) == 1:
            logger.warning("Nenhuma chave cloud configurada — chain usa apenas Ollama.")

        return chain

    # ------------------------------------------------------------------ #
    #  Pipeline entry point                                                 #
    # ------------------------------------------------------------------ #

    async def process_edital(self, content_hash: str, md_content: str) -> dict:
        """Orquestra CargoTitleAgent → CargoVitaminizerAgent → SubjectsScoutAgent.

        Injeta a chain de providers em cada agente.
        Retorna dict com 'edital' (EditalGeral) e 'cargos' (List[Cargo]).
        """
        chain = self._get_provider_chain()
        logger.info(
            "process_edital [%s]: chain=[%s]",
            content_hash[:12],
            ", ".join(p.__class__.__name__ for p in chain),
        )

        cargos = await self.cargo_agent.hunt_titles(content_hash, chain)
        vitamin_data = await self.vitaminizer_agent.vitaminize(content_hash, cargos, chain)
        cargos_com_materias = await self.subjects_scout_agent.scout(
            content_hash, vitamin_data.cargos_vitaminados, chain
        )

        return {"edital": vitamin_data.edital_info, "cargos": cargos_com_materias}

    # ------------------------------------------------------------------ #
    #  LLM extraction (kept for backwards-compat / direct chunk use)       #
    # ------------------------------------------------------------------ #

    async def _extract_from_chunk(self, chunk: str) -> Optional[EditalGeral]:
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
                logger.info("Tentando provider %s...", provider.__class__.__name__)
                log_streamer.broadcast({"type": "log", "message": f"🤖 IA: Tentando extração com {provider.__class__.__name__}...", "level": "INFO"})
                result: EditalGeral = await provider.generate_json(prompt=prompt, schema=EditalGeral)
                logger.info("Provider %s respondeu com sucesso.", provider.__class__.__name__)
                return result
            except Exception as e:
                logger.warning("⚠️ %s falhou, tentando próximo: %s", provider.__class__.__name__, e)
                log_streamer.broadcast({"type": "log", "message": f"⚠️ {provider.__class__.__name__} falhou, tentando próximo...", "level": "WARNING"})
        return None

    # ------------------------------------------------------------------ #
    #  Merge helpers                                                        #
    # ------------------------------------------------------------------ #

    @staticmethod
    def _merge_materias(existing: List[Materia], incoming: List[Materia]) -> List[Materia]:
        seen = {m.nome: m for m in existing}
        for m in incoming:
            if m.nome not in seen:
                seen[m.nome] = m
        return list(seen.values())

    @staticmethod
    def _merge_cargos(base: List[Cargo], incoming: List[Cargo]) -> List[Cargo]:
        index = {c.titulo: c for c in base}
        for cargo in incoming:
            if cargo.titulo in index:
                merged = AIService._merge_materias(index[cargo.titulo].materias, cargo.materias)
                index[cargo.titulo] = index[cargo.titulo].model_copy(update={"materias": merged})
            else:
                index[cargo.titulo] = cargo
        return list(index.values())

    # ------------------------------------------------------------------ #
    #  Database persistence                                                 #
    # ------------------------------------------------------------------ #

    @staticmethod
    def _create_edital_sync(result: EditalGeral) -> Optional[int]:
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
            logger.info("Edital '%s' criado no banco (id=%s).", result.orgao, edital_db.id)
            return edital_db.id
        except Exception as e:
            logger.error("Falha ao criar Edital no banco: %s", e)
            db.rollback()
            return None
        finally:
            db.close()

    @staticmethod
    def _persist_cargos_sync(edital_db_id: int, cargos: List[Cargo], known_titulos: Set[str]) -> List[dict]:
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
                    materia_db = db_models.Materia(cargo_id=cargo_db.id, nome=materia_schema.nome)
                    db.add(materia_db)
                    db.flush()
                    for topico_str in materia_schema.topicos:
                        db.add(db_models.Topico(materia_id=materia_db.id, conteudo=topico_str))
                db.commit()
                known_titulos.add(cargo_schema.titulo)
                saved.append(cargo_schema.model_dump())
        except Exception as e:
            logger.error("Falha ao persistir cargos (edital_id=%s): %s", edital_db_id, e)
            db.rollback()
        finally:
            db.close()
        return saved

    async def _create_edital_db(self, result: EditalGeral) -> Optional[int]:
        return await asyncio.to_thread(self._create_edital_sync, result)

    async def _persist_and_broadcast(self, edital_db_id: int, cargos: List[Cargo], known_titulos: Set[str]) -> None:
        saved = await asyncio.to_thread(self._persist_cargos_sync, edital_db_id, cargos, known_titulos)
        for cargo_dict in saved:
            logger.info("Cargo '%s' extraído e salvo!", cargo_dict["titulo"])
            log_streamer.broadcast({"type": "data", "payload": cargo_dict})

    # ------------------------------------------------------------------ #
    #  Legacy chunked extraction (kept for backwards-compat)               #
    # ------------------------------------------------------------------ #

    async def extract_edital_data(self, md_content: str) -> EditalResponse:
        if len(md_content) <= CHUNK_THRESHOLD:
            logger.info("Edital pequeno (%d chars) — processamento direto.", len(md_content))
            result = await self._extract_from_chunk(md_content)
            if result is None:
                raise RuntimeError("Todos os providers LLM falharam na extração.")
            edital_db_id = await self._create_edital_db(result)
            if edital_db_id:
                await self._persist_and_broadcast(edital_db_id, result.cargos, set())
            return EditalResponse(**result.model_dump(), id=edital_db_id, status=StatusEdital.INGESTADO)

        chunker = MarkdownChunker(chunk_size=CHUNK_SIZE, overlap=CHUNK_OVERLAP)
        chunks = chunker.split(md_content)
        total = len(chunks)
        logger.info("Edital grande (%d chars) dividido em %d chunks.", len(md_content), total)

        merged: Optional[EditalGeral] = None
        edital_db_id: Optional[int] = None
        known_titulos: Set[str] = set()
        failed_chunks: List[int] = []

        for idx, chunk in enumerate(chunks, start=1):
            logger.info("Processando chunk %d/%d (%d chars)...", idx, total, len(chunk))
            result = await self._extract_from_chunk(chunk)
            await asyncio.sleep(2.0)

            if result is None:
                logger.warning("Chunk %d/%d falhou — pulando.", idx, total)
                failed_chunks.append(idx)
                continue

            if merged is None:
                merged = result
                edital_db_id = await self._create_edital_db(result)
                if edital_db_id:
                    await self._persist_and_broadcast(edital_db_id, result.cargos, known_titulos)
            else:
                new_cargos = [c for c in result.cargos if c.titulo not in known_titulos]
                if edital_db_id and new_cargos:
                    await self._persist_and_broadcast(edital_db_id, new_cargos, known_titulos)
                merged_cargos = self._merge_cargos(merged.cargos, result.cargos)
                merged = merged.model_copy(update={"cargos": merged_cargos})

        if merged is None or not merged.cargos:
            raise RuntimeError(f"Extração em chunks não produziu cargos. Chunks falhos: {failed_chunks}/{total}")

        if failed_chunks:
            logger.warning("Extração concluída com %d chunk(s) falho(s): %s", len(failed_chunks), failed_chunks)

        return EditalResponse(**merged.model_dump(), id=edital_db_id, status=StatusEdital.INGESTADO)
