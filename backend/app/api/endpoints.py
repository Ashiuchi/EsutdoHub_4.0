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

        # 2. Processamento Subtrativo
        _broadcast_log(content_hash, "Iniciando processamento subtrativo…")
        enxuto_md, fragments = subtractive_agent.process(md_content)

        # 3. Persistência em Disco
        result_data = StorageResult(
            content_hash=content_hash,
            stripped_md=enxuto_md,
            tables={k: v for k, v in fragments.items() if k.startswith("FRAGMENT_TABLE_")},
            patterns={k: v for k, v in fragments.items() if not k.startswith("FRAGMENT_TABLE_")}
        )
        storage_path = subtractive_agent.persist(result_data)
        _broadcast_log(content_hash, f"Edital persistido em: {storage_path}")

        # 4. Orquestração de IA (CargoTitle → Vitaminizer → SubjectsScout)
        _broadcast_log(content_hash, "Iniciando inteligência artificial (Pipeline Agnostico)…")
        result = await ai_service.process_edital(content_hash, enxuto_md)

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
    
    Retorna imediatamente com status 'processando'.
    """
    file_bytes = await file.read()
    content_hash = _compute_hash(file_bytes)
    
    # Salvar temporariamente para o background task ler
    temp_path = f"temp_{content_hash}_{uuid.uuid4().hex[:8]}.pdf"
    async with aiofiles.open(temp_path, "wb") as buffer:
        await buffer.write(file_bytes)

    # Disparar tarefa em background
    background_tasks.add_task(_process_edital_task, content_hash, temp_path)

    # Retorno imediato
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
