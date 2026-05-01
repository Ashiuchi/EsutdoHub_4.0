import asyncio
import logging
import uuid
from pathlib import Path
from typing import Dict, List, Optional, Set, Tuple

from app.core.config import settings
from app.core.logging_streamer import log_streamer
from app.db import models as db_models
from app.db.database import SessionLocal
from app.providers.base_provider import BaseLLMProvider
from app.providers.gemini_provider import GeminiProvider
from app.providers.ollama_provider import OllamaProvider
from app.providers.groq_provider import GroqProvider
from app.providers.openrouter_provider import OpenRouterProvider
from app.schemas.edital_schema import Cargo, EditalGeral, EditalResponse, Materia, StatusEdital
from app.services.chunker_service import MarkdownChunker
from app.services.cargo_mapper import CargoMapper, CargoSeed
from app.services.cargo_anchor import AnchorEngine
from app.services.cargo_specialist import CargoTitleAgent
from app.services.cargo_vitaminizer import CargoVitaminizerAgent
from app.services.cargo_auditor import CargoAuditorAgent
from app.services.subjects_scout import SubjectsScoutAgent

# type alias for enrichment map: topic_text -> (embedding, canonical_topic_id | None)
_TopicEnrichments = Dict[str, Tuple[List[float], Optional[uuid.UUID]]]

logger = logging.getLogger(__name__)

CHUNK_THRESHOLD = 15_000
CHUNK_SIZE = 15_000
CHUNK_OVERLAP = 1_000


class AIService:
    """Orquestra provider chain, pipeline de agentes e persistência incremental."""

    _lock = asyncio.Lock()
    _manual_active_count = 0

    def __init__(self) -> None:
        _key = settings.gemini_api_key
        _key_preview = f"{_key[:4]}...{_key[-4:]}" if _key and len(_key) >= 8 else (_key or "None")
        logger.debug(f"AIService.__init__: settings.gemini_api_key = {_key_preview}")

        self.ollama_provider = OllamaProvider(model="llama3.2:3b")
        self.groq_provider = GroqProvider()
        self.openrouter_provider = OpenRouterProvider()
        self.gemini_provider = GeminiProvider()

        self.cargo_mapper = CargoMapper()
        self.cargo_anchor = AnchorEngine()
        self.cargo_agent = CargoTitleAgent()
        self.vitaminizer_agent = CargoVitaminizerAgent()
        self.cargo_auditor = CargoAuditorAgent()
        self.subjects_scout_agent = SubjectsScoutAgent()

        _initial_chain = self._get_provider_chain()
        logger.info("AIService initialized — chain: %s", " → ".join(p.__class__.__name__ for p in _initial_chain))

    # ------------------------------------------------------------------ #
    #  Provider chain                                                       #
    # ------------------------------------------------------------------ #

    def _get_provider_chain(self) -> List[BaseLLMProvider]:
        """Constrói lista ordenada: Ollama sempre primeiro, cloud providers se tiverem chave."""
        chain: List[BaseLLMProvider] = [self.ollama_provider]

        if settings.groq_api_key:
            chain.append(self.groq_provider)
        if settings.openrouter_api_key:
            chain.append(self.openrouter_provider)
        if settings.gemini_api_key:
            chain.append(self.gemini_provider)

        if len(chain) == 1:
            logger.warning("Nenhuma chave cloud configurada — chain usa apenas Ollama.")

        return chain

    @staticmethod
    def _resolve_storage(content_hash: str) -> Optional[Path]:
        for candidate in [
            Path("backend/storage/processed") / content_hash,
            Path("storage/processed") / content_hash,
            Path("/app/storage/processed") / content_hash,
        ]:
            if candidate.exists():
                return candidate
        return None

    # ------------------------------------------------------------------ #
    #  Pipeline entry point                                                 #
    # ------------------------------------------------------------------ #

    async def process_edital(self, content_hash: str, md_content: str, fingerprint: Optional[str] = None, is_manual: bool = False) -> dict:
        """Orquestra o pipeline de IA com sistema de prioridade.
        
        Processos manuais (upload) têm precedência. Processos em massa (Moenda) 
        aguardam se houver uploads em andamento.
        """
        if is_manual:
            AIService._manual_active_count += 1
            try:
                async with AIService._lock:
                    return await self._process_edital_core(content_hash, md_content, fingerprint)
            finally:
                AIService._manual_active_count -= 1
        else:
            # Moenda Industrial / Massa
            while AIService._manual_active_count > 0:
                logger.info("Moenda [%s]: Aguardando conclusão de processos manuais prioritários...", content_hash[:8])
                await asyncio.sleep(5)
            
            async with AIService._lock:
                return await self._process_edital_core(content_hash, md_content, fingerprint)

    async def _process_edital_core(self, content_hash: str, md_content: str, fingerprint: Optional[str] = None) -> dict:
        """Lógica interna original de processamento."""
        chain = self._get_provider_chain()
        logger.info(
            "process_edital [%s]: chain=[%s] fingerprint=[%s]",
            content_hash[:12],
            ", ".join(p.__class__.__name__ for p in chain),
            fingerprint
        )

        storage_path = self._resolve_storage(content_hash)
        if storage_path is None:
            logger.error("process_edital [%s]: storage path not found", content_hash[:12])
            return {"edital": None, "cargos": [], "id": None}

        seeds = self.cargo_mapper.map(content_hash)
        if seeds:
            logger.info("CargoMapper [%s]: %d seeds determinísticos.", content_hash[:12], len(seeds))
        else:
            logger.info("CargoMapper [%s]: nenhum seed → acionando LLM fallback.", content_hash[:12])
            seeds = await self._llm_seed_fallback(content_hash, chain)

        # Camada 2: Ancoragem de Texto (AnchorEngine)
        main_md = (storage_path / "main.md").read_text(encoding="utf-8") if (storage_path / "main.md").exists() else ""
        
        seed_titles = [s.titulo for s in seeds]
        cargo_contexts = self.cargo_anchor.anchor(main_md, seed_titles, storage_path=storage_path)
        logger.info("AnchorEngine [%s]: %d contextos ancorados.", content_hash[:12], len(cargo_contexts))

        cargos = await self.cargo_agent.hunt_titles(content_hash, chain)
        cargos = self._merge_seeds_into_cargos(seeds, cargos)
        
        vitamin_data = await self.vitaminizer_agent.vitaminize(content_hash, cargos, chain, cargo_contexts=cargo_contexts)

        # Raio-X de qualidade: descarta ruído, separa aprovados de quarentena
        audit_results = self.cargo_auditor.audit(vitamin_data.cargos_vitaminados)
        approved    = [r.cargo for r in audit_results if not r.is_noise and r.verdict == "aprovado"]
        quarantined = [r.cargo for r in audit_results if not r.is_noise and r.verdict == "quarentena"]
        
        for a in approved:
            a.status = "vitaminado"
        for q in quarantined:
            q.status = "quarentena"
        logger.info(
            "CargoAuditor [%s]: %d aprovado(s), %d quarentena, %d ruído descartado.",
            content_hash[:12], len(approved), len(quarantined),
            len(audit_results) - len(approved) - len(quarantined),
        )

        # SubjectsScout processa apenas aprovados
        cargos_com_materias = await self.subjects_scout_agent.scout(
            content_hash, approved, chain, cargo_contexts=cargo_contexts
        )

        # Injetar o hash para persistência e vincular ao storage
        vitamin_data.edital_info.content_hash = content_hash
        vitamin_data.edital_info.fingerprint = fingerprint

        # Enriquecer tópicos com embeddings + canonical IDs antes de persistir
        all_cargos_to_persist = cargos_com_materias + quarantined
        topic_enrichments = await self._enrich_topics(all_cargos_to_persist)

        # Persistência no Banco de Dados
        edital_db_id = await self._create_edital_db(vitamin_data.edital_info)
        if edital_db_id:
            await self._persist_and_broadcast(
                edital_db_id, all_cargos_to_persist, set(),
                cargo_contexts=cargo_contexts,
                topic_enrichments=topic_enrichments,
            )

        return {"edital": vitamin_data.edital_info, "cargos": all_cargos_to_persist, "id": edital_db_id}

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
    def _merge_seeds_into_cargos(seeds: List[CargoSeed], llm_cargos: List) -> List:
        if not seeds:
            return llm_cargos
        def _norm(s: str) -> str:
            import unicodedata
            t = unicodedata.normalize("NFD", s.lower())
            t = "".join(c for c in t if unicodedata.category(c) != "Mn")
            import re
            return re.sub(r"[\s\-–/]+", " ", t).strip()
        index = {_norm(c.titulo): c for c in llm_cargos}
        for seed in seeds:
            key = _norm(seed.titulo)
            if key in index:
                cargo = index[key]
                if not getattr(cargo, "codigo_edital", None) and seed.codigo:
                    cargo.codigo_edital = seed.codigo
            else:
                from app.schemas.edital_schema import CargoIdentificado
                index[key] = CargoIdentificado(titulo=seed.titulo, codigo_edital=seed.codigo)
        return list(index.values())

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

    async def _llm_seed_fallback(self, content_hash: str, chain: List[BaseLLMProvider]) -> List[CargoSeed]:
        from app.services.cargo_mapper import CargoSeed
        from app.schemas.edital_schema import CargoIdentificado
        from pydantic import BaseModel
        storage = self._resolve_storage(content_hash)
        if storage is None: return []
        main_md = storage / "main.md"
        if not main_md.exists(): return []
        excerpt = main_md.read_text(encoding="utf-8")[:3_000]
        prompt = (
            "Analise o início do edital de concurso público abaixo.\n"
            "Liste APENAS os nomes dos cargos ou funções mencionados.\n"
            'Responda EXCLUSIVAMENTE em JSON: {"cargos": [{"titulo": "nome do cargo", "codigo_edital": null}]}\n\n'
            f"EDITAL (início):\n{excerpt}"
        )
        class _CargoList(BaseModel):
            cargos: List[CargoIdentificado]
        for provider in chain:
            try:
                result: _CargoList = await provider.generate_json(prompt=prompt, schema=_CargoList)
                if result.cargos:
                    return [CargoSeed(titulo=c.titulo, codigo=c.codigo_edital, source_file="llm_fallback") for c in result.cargos]
            except Exception as exc:
                logger.warning("LLM seed fallback %s falhou: %s", provider.__class__.__name__, exc)
        return []

    # ------------------------------------------------------------------ #
    #  Topic enrichment (embed + canonicalize)                             #
    # ------------------------------------------------------------------ #

    async def _enrich_topics(self, cargos: List[Cargo]) -> "_TopicEnrichments":
        """Gera embeddings e canonical IDs para todos os tópicos únicos dos cargos.

        Usa OllamaProvider (bge-m3 local, 1024d) para manter espaço vetorial único
        com os dados retroativos. Semaphore(20) por ser chamada local sem rate-limit.
        Retorna {} silenciosamente se o Ollama não estiver acessível.
        """
        from app.services.canonicalizer_service import CanonicalizerService

        unique_topics: Set[str] = {
            t
            for cargo in cargos
            for materia in cargo.materias
            for t in materia.topicos
            if t and t.strip()
        }
        if not unique_topics:
            return {}

        db = SessionLocal()
        canonicalizer = CanonicalizerService(db, self.ollama_provider)
        semaphore = asyncio.Semaphore(20)
        enrichments: _TopicEnrichments = {}

        async def _enrich_one(topic: str) -> None:
            async with semaphore:
                try:
                    embedding = await self.ollama_provider.embed_text(topic)
                    canonical, _ = await canonicalizer.canonicalize(topic, embedding=embedding)
                    enrichments[topic] = (embedding, canonical.id if canonical else None)
                except Exception as exc:
                    logger.warning("Topic enrichment failed '%s…': %s", topic[:50], exc)

        try:
            await asyncio.gather(*[_enrich_one(t) for t in unique_topics])
        finally:
            db.close()

        matched = sum(1 for _, cid in enrichments.values() if cid is not None)
        logger.info(
            "Topic enrichment: %d/%d enriched, %d canonical matches",
            len(enrichments), len(unique_topics), matched,
        )
        return enrichments

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
                content_hash=result.content_hash,
                fingerprint=result.fingerprint,
                status=StatusEdital.INGESTADO,
            )
            db.add(edital_db)
            db.commit()
            db.refresh(edital_db)
            return edital_db.id
        except Exception as e:
            logger.error("Falha ao criar Edital no banco: %s", e)
            db.rollback()
            return None
        finally:
            db.close()

    @staticmethod
    def _persist_cargos_sync(
        edital_db_id: int,
        cargos: List[Cargo],
        known_titulos: Set[str],
        cargo_contexts: Optional[dict] = None,
        topic_enrichments: Optional["_TopicEnrichments"] = None,
    ) -> List[dict]:
        saved: List[dict] = []
        enrichments = topic_enrichments or {}
        db = SessionLocal()
        try:
            for cargo_schema in cargos:
                if cargo_schema.titulo in known_titulos:
                    continue
                anchor = (cargo_contexts or {}).get(cargo_schema.titulo)
                cargo_db = db_models.Cargo(
                    edital_id=edital_db_id,
                    titulo=cargo_schema.titulo,
                    salario=cargo_schema.salario,
                    requisitos=cargo_schema.requisitos,
                    anchor_text=anchor,
                    syllabus_score=getattr(cargo_schema, "syllabus_score", None),
                    status=getattr(cargo_schema, "status", "extraido"),
                    price=0.0,
                )
                db.add(cargo_db)
                db.flush()
                for materia_schema in cargo_schema.materias:
                    materia_db = db_models.Materia(cargo_id=cargo_db.id, nome=materia_schema.nome)
                    db.add(materia_db)
                    db.flush()
                    for topico_str in materia_schema.topicos:
                        emb, canon_id = enrichments.get(topico_str, (None, None))
                        db.add(db_models.Topico(
                            materia_id=materia_db.id,
                            conteudo=topico_str,
                            embedding=emb,
                            canonical_topic_id=canon_id,
                        ))
                db.commit()
                known_titulos.add(cargo_schema.titulo)
                saved.append(cargo_schema.model_dump())
        except Exception as e:
            logger.error("Falha ao persistir cargos: %s", e)
            db.rollback()
        finally:
            db.close()
        return saved

    async def _create_edital_db(self, result: EditalGeral) -> Optional[int]:
        return await asyncio.to_thread(self._create_edital_sync, result)

    async def _persist_and_broadcast(
        self,
        edital_db_id: int,
        cargos: List[Cargo],
        known_titulos: Set[str],
        cargo_contexts: Optional[dict] = None,
        topic_enrichments: Optional["_TopicEnrichments"] = None,
    ) -> None:
        saved = await asyncio.to_thread(
            self._persist_cargos_sync,
            edital_db_id, cargos, known_titulos, cargo_contexts, topic_enrichments,
        )
        for cargo_dict in saved:
            log_streamer.broadcast({"type": "data", "payload": cargo_dict})

    async def extract_edital_data(self, md_content: str) -> EditalResponse:
        # Simplificado para manter consistência com o novo pipeline
        chunker = MarkdownChunker(chunk_size=CHUNK_SIZE, overlap=CHUNK_OVERLAP)
        chunks = chunker.split(md_content)
        # ... logic for legacy chunking would go here if needed ...
        # For brevity and safety after crash, we prioritize the new agent-based pipeline.
        return EditalResponse(orgao="Extração Legada", banca="N/A", cargos=[], content_hash="N/A")
