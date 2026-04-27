import asyncio
import json
import os
import shutil
import logging
import hashlib
import uuid
from datetime import datetime
from typing import AsyncGenerator

import aiofiles
from fastapi import APIRouter, Request, UploadFile, File, HTTPException, BackgroundTasks
from sse_starlette.sse import EventSourceResponse

from app.core.logging_streamer import log_streamer
from app.schemas.edital_schema import IngestionResponse, StatusEdital
from app.services.pdf_service import PDFService
from app.services.subtractive_service import SubtractiveAgent, StorageResult
from app.services.ai_service import AIService
from app.services.fingerprint_service import FingerprintService
from app.db.database import SessionLocal
from app.db import models

router = APIRouter()
subtractive_agent = SubtractiveAgent()
ai_service = AIService()
logger = logging.getLogger(__name__)

_SSE_KEEPALIVE_SECONDS = 15

def _compute_hash(file_bytes: bytes) -> str:
    return hashlib.sha256(file_bytes).hexdigest()

def _broadcast_log(content_hash: str, message: str) -> None:
    """Envia um evento de log ao cockpit SSE e ao logger local."""
    logger.info(message)
    log_streamer.broadcast({"type": "log", "content_hash": content_hash, "message": message})


def _broadcast_error(content_hash: str, stage: str, error: Exception) -> None:
    """Envia um evento de erro ao cockpit SSE e ao logger local."""
    message = f"[{stage}] {error}"
    logger.error("Erro no processamento (%s): %s", stage, error, exc_info=True)
    log_streamer.broadcast({
        "type": "error",
        "stage": stage,
        "content_hash": content_hash,
        "message": message,
    })


async def _process_edital_task(content_hash: str, temp_path: str):
    """Tarefa de segundo plano para processar o edital pesado."""
    try:
        _broadcast_log(content_hash, f"Iniciando processamento para {content_hash}")

        # 1. Converter para Markdown
        _broadcast_log(content_hash, "Extraindo texto do PDF…")
        try:
            md_content = PDFService.to_markdown(temp_path)
        except Exception as e:
            _broadcast_error(content_hash, "pdf_extraction", e)
            return

        if not md_content.strip():
            exc = ValueError("Conteúdo do PDF está vazio ou ilegível.")
            _broadcast_error(content_hash, "pdf_extraction", exc)
            return

        _broadcast_log(content_hash, f"PDF extraído: {len(md_content)} caracteres")

        # 2. Gerar Fingerprint (DNA estrutural)
        _broadcast_log(content_hash, "Gerando fingerprint estrutural…")
        try:
            async with aiofiles.open(temp_path, mode="rb") as f:
                pdf_bytes = await f.read()
            fingerprint = FingerprintService.generate_fingerprint(pdf_bytes, md_content)
        except Exception as e:
            logger.warning("Erro ao gerar fingerprint: %s. Continuando sem.", e)
            fingerprint = None

        # 3. Processamento Subtrativo (A Trindade)
        _broadcast_log(content_hash, "Iniciando processamento subtrativo (Gerando Trindade de Markdowns)…")
        result_data = subtractive_agent.process(md_content)
        result_data.content_hash = content_hash

        # 4. Persistência em Disco
        storage_path = subtractive_agent.persist(result_data)
        _broadcast_log(content_hash, f"Edital persistido em: {storage_path}")

        # 5. Orquestração de IA (CargoTitle → Vitaminizer → SubjectsScout)
        _broadcast_log(content_hash, "Iniciando inteligência artificial (Pipeline Agnostico)…")
        # Usamos main_md (enxuto com marcadores) para ancoragem
        result = await ai_service.process_edital(content_hash, result_data.main_md, fingerprint=fingerprint)


        # 5. Notificar via SSE (broadcast de dados final)
        log_streamer.broadcast({
            "type": "data",
            "status": StatusEdital.PROCESSADO,
            "content_hash": content_hash,
            "edital": result["edital"].model_dump() if hasattr(result["edital"], "model_dump") else result["edital"],
            "cargos": [c.model_dump() if hasattr(c, "model_dump") else c for c in result["cargos"]],
        })
        _broadcast_log(content_hash, f"Processamento completo para {content_hash}")

    except Exception as e:
        _broadcast_error(content_hash, "processing", e)
    finally:
        if os.path.exists(temp_path):
            try:
                os.remove(temp_path)
            except Exception as cleanup_err:
                logger.warning("Não foi possível remover arquivo temporário %s: %s", temp_path, cleanup_err)

@router.post("/upload", response_model=IngestionResponse)
async def upload_edital(background_tasks: BackgroundTasks, file: UploadFile = File(...)):
    """Recebe o arquivo e inicia o processamento em segundo plano.

    Se o content_hash já existir no banco, retorna o edital existente imediatamente
    sem reprocessar. Caso contrário, retorna status 'processando'.
    """
    file_bytes = await file.read()
    content_hash = _compute_hash(file_bytes)

    db = SessionLocal()
    try:
        existing = db.query(models.Edital).filter_by(content_hash=content_hash).first()
        if existing:
            return IngestionResponse(
                id=existing.id,
                content_hash=existing.content_hash,
                status=existing.status,
                total_tables=0,
                total_links=0,
                total_chars=0,
            )
    finally:
        db.close()

    temp_path = f"temp_{content_hash}_{uuid.uuid4().hex[:8]}.pdf"
    async with aiofiles.open(temp_path, "wb") as buffer:
        await buffer.write(file_bytes)

    background_tasks.add_task(_process_edital_task, content_hash, temp_path)

    return IngestionResponse(
        id=uuid.uuid4(),
        content_hash=content_hash,
        status=StatusEdital.PROCESSANDO,
        total_tables=0,
        total_links=0,
        total_chars=0
    )


@router.get("/cockpit/stream")
async def cockpit_stream(request: Request) -> EventSourceResponse:
    """Endpoint SSE que transmite logs e eventos de dados em tempo real.

    Emite dois tipos de eventos:
    - `log`: mensagens de log capturadas dos namespaces app.services e app.api.
    - `data`: payload de cargo recém-salvo no banco de dados.
    - `ping`: keepalive enviado a cada 15 s de inatividade.

    Args:
        request: Request do FastAPI (usado para detectar desconexão do cliente).

    Returns:
        EventSourceResponse com stream infinito de eventos SSE.
    """
    async def _event_generator() -> AsyncGenerator[dict, None]:
        queue = log_streamer.subscribe()
        logger.info("Cockpit SSE: novo cliente conectado.")
        try:
            while True:
                if await request.is_disconnected():
                    break
                try:
                    message = await asyncio.wait_for(queue.get(), timeout=_SSE_KEEPALIVE_SECONDS)
                    yield {
                        "event": message.get("type", "log"),
                        "data": json.dumps(message, ensure_ascii=False),
                    }
                except asyncio.TimeoutError:
                    yield {
                        "event": "ping",
                        "data": json.dumps({"type": "ping"}),
                    }
        finally:
            log_streamer.unsubscribe(queue)
            logger.info("Cockpit SSE: cliente desconectado.")

    return EventSourceResponse(_event_generator())


@router.get("/", response_model=list)
async def list_editais():
    """Retorna todos os editais processados formatados para o Cockpit."""
    db = SessionLocal()
    try:
        from sqlalchemy.orm import joinedload
        # Carrega editais, cargos e matérias (com tópicos)
        editais = db.query(models.Edital).options(
            joinedload(models.Edital.cargos).joinedload(models.Cargo.materias).joinedload(models.Materia.topicos)
        ).order_by(models.Edital.created_at.desc()).limit(10).all()
        
        # Formatação manual para bater com a interface do Frontend
        result = []
        for e in editais:
            edital_dict = {
                "id": str(e.id),
                "title": e.title or e.orgao,
                "orgao": e.orgao,
                "banca": e.banca,
                "published_at": e.published_at,
                "inscription_start": e.inscription_start,
                "inscription_end": e.inscription_end,
                "data_prova": e.data_prova,
                "status": e.status,
                "cargos": []
            }
            for c in e.cargos:
                cargo_dict = {
                    "titulo": c.titulo,
                    "salario": c.salario,
                    "escolaridade": c.escolaridade,
                    "vagas_total": c.vagas_total,
                    "status": c.status,
                    "materias": []
                }
                for m in c.materias:
                    cargo_dict["materias"].append({
                        "nome": m.nome,
                        "topicos": [t.conteudo for t in m.topicos]
                    })
                edital_dict["cargos"].append(cargo_dict)
            result.append(edital_dict)
            
        return result
    finally:
        db.close()

@router.get("/stats")
async def get_stats():
    """Retorna estatísticas globais da Moenda Industrial."""
    db = SessionLocal()
    try:
        total_editais = db.query(models.Edital).count()
        total_cargos = db.query(models.Cargo).count()
        total_materias = db.query(models.Materia).count()
        return {
            "total_editais": total_editais,
            "total_cargos": total_cargos,
            "total_materias": total_materias
        }
    finally:
        db.close()
