import asyncio
import json
import os
import shutil
import logging
import hashlib
import uuid
from datetime import datetime
from typing import AsyncGenerator

from fastapi import APIRouter, Request, UploadFile, File, HTTPException
from sse_starlette.sse import EventSourceResponse

from app.core.logging_streamer import log_streamer
from app.schemas.edital_schema import IngestionResponse, StatusEdital
from app.services.pdf_service import PDFService
from app.services.subtractive_service import SubtractiveAgent, StorageResult

router = APIRouter()
subtractive_agent = SubtractiveAgent()
logger = logging.getLogger(__name__)

_SSE_KEEPALIVE_SECONDS = 15

def _compute_hash(file_bytes: bytes) -> str:
    return hashlib.sha256(file_bytes).hexdigest()

@router.post("/upload", response_model=IngestionResponse)
async def upload_edital(file: UploadFile = File(...)):
    """Ingestão silenciosa do edital usando SubtractiveAgent.
    
    Não utiliza LLM nesta fase.
    """
    file_bytes = await file.read()
    content_hash = _compute_hash(file_bytes)
    
    temp_path = f"temp_{content_hash}.pdf"
    with open(temp_path, "wb") as buffer:
        buffer.write(file_bytes)

    try:
        # 1. Converter para Markdown
        md_content = PDFService.to_markdown(temp_path)
        if not md_content.strip():
            raise ValueError("Conteúdo do PDF está vazio ou ilegível.")

        # 2. Processamento Subtrativo
        enxuto_md, fragments = subtractive_agent.process(md_content)
        
        # 3. Persistência em Disco
        result_data = StorageResult(
            content_hash=content_hash,
            stripped_md=enxuto_md,
            tables={k: v for k, v in fragments.items() if k.startswith("FRAGMENT_TABLE_")},
            patterns={k: v for k, v in fragments.items() if not k.startswith("FRAGMENT_TABLE_")}
        )
        storage_path = subtractive_agent.persist(result_data)
        logger.info(f"Edital persistido em: {storage_path}")

        # 4. (Placeholder) Salvar no Banco - Como não temos DB session injetada aqui via Depends,
        # vamos retornar um ID gerado agora. Em uma Task futura, integraremos com SQLAlchemy.
        fake_id = uuid.uuid4()

        return IngestionResponse(
            id=fake_id,
            content_hash=content_hash,
            status=StatusEdital.INGESTADO,
            total_tables=len(result_data.tables),
            total_links=len(fragments.get("links", [])),
            total_chars=len(enxuto_md)
        )

    except Exception as e:
        logger.error(f"Erro na Ingestão: {str(e)}", exc_info=True)
        raise HTTPException(
            status_code=500,
            detail=f"Falha ao processar o edital: {str(e)}",
        )
    finally:
        if os.path.exists(temp_path):
            os.remove(temp_path)


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
