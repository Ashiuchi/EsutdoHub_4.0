import hashlib
import logging
import os
import uuid

from fastapi import APIRouter, BackgroundTasks, Depends, File, HTTPException, UploadFile

from app.core.auth import verify_clerk_token
from app.db.database import SessionLocal
from app.db import models

router = APIRouter(prefix="/biblioteca", tags=["Biblioteca"])
logger = logging.getLogger(__name__)

_STORAGE_ROOT = "/app/storage/biblioteca"


def _user_dir(user_id: str) -> str:
    path = os.path.join(_STORAGE_ROOT, user_id)
    os.makedirs(path, exist_ok=True)
    return path


def _extract_text_task(item_id: str, file_path: str) -> None:
    """Extrai texto do PDF via PyMuPDF e atualiza o status no banco.

    Roda em background depois que a resposta HTTP já foi enviada.
    """
    import fitz  # PyMuPDF — disponível no container

    db = SessionLocal()
    item = None
    try:
        item = db.query(models.BibliotecaItem).filter(
            models.BibliotecaItem.id == uuid.UUID(item_id)
        ).first()
        if not item:
            logger.warning("BibliotecaItem %s não encontrado para extração.", item_id)
            return

        doc = fitz.open(file_path)
        pages_text = [page.get_text() for page in doc]
        full_text = "\n\n".join(pages_text)
        page_count = doc.page_count
        doc.close()

        text_path = file_path.rsplit(".", 1)[0] + "_extracted.txt"
        with open(text_path, "w", encoding="utf-8") as f:
            f.write(full_text)

        item.status = "concluido"
        item.page_count = page_count
        db.commit()
        logger.info("Extração concluída — item %s (%d páginas, %d chars)", item_id, page_count, len(full_text))

    except Exception as exc:
        logger.error("Erro ao extrair texto [%s]: %s", item_id, exc, exc_info=True)
        if item:
            try:
                item.status = "erro"
                db.commit()
            except Exception:
                pass
    finally:
        db.close()


@router.post("/upload")
async def upload_biblioteca(
    background_tasks: BackgroundTasks,
    file: UploadFile = File(...),
    payload: dict = Depends(verify_clerk_token),
):
    """Recebe um PDF, salva em storage isolado por usuário e inicia extração de texto."""
    user_id: str = payload.get("sub", "")
    if not user_id:
        raise HTTPException(status_code=401, detail="Usuário não identificado.")

    if not file.filename or not file.filename.lower().endswith(".pdf"):
        raise HTTPException(status_code=400, detail="Apenas arquivos PDF são aceitos.")

    file_bytes = await file.read()
    file_size = len(file_bytes)
    content_hash = hashlib.sha256(file_bytes).hexdigest()

    db = SessionLocal()
    try:
        existing = db.query(models.BibliotecaItem).filter(
            models.BibliotecaItem.user_id == user_id,
            models.BibliotecaItem.content_hash == content_hash,
        ).first()
        if existing:
            return _serialize(existing)

        storage_dir = _user_dir(user_id)
        safe_name = f"{uuid.uuid4().hex[:8]}_{file.filename}"
        file_path = os.path.join(storage_dir, safe_name)

        with open(file_path, "wb") as f:
            f.write(file_bytes)

        item = models.BibliotecaItem(
            user_id=user_id,
            filename=file.filename,
            file_size=file_size,
            content_hash=content_hash,
            file_path=file_path,
            status="processando",
        )
        db.add(item)
        db.commit()
        db.refresh(item)

        background_tasks.add_task(_extract_text_task, str(item.id), file_path)
        logger.info("Arquivo '%s' recebido para usuário %s (%.1f KB)", file.filename, user_id[:8], file_size / 1024)

        return _serialize(item)
    finally:
        db.close()


@router.get("/")
async def list_biblioteca(payload: dict = Depends(verify_clerk_token)):
    """Lista os materiais de estudo do usuário autenticado (metadados apenas)."""
    user_id: str = payload.get("sub", "")
    if not user_id:
        raise HTTPException(status_code=401, detail="Usuário não identificado.")

    db = SessionLocal()
    try:
        items = (
            db.query(models.BibliotecaItem)
            .filter(models.BibliotecaItem.user_id == user_id)
            .order_by(models.BibliotecaItem.created_at.desc())
            .all()
        )
        return [_serialize(i) for i in items]
    finally:
        db.close()


def _serialize(item: models.BibliotecaItem) -> dict:
    """Retorna apenas metadados — file_path nunca exposto."""
    return {
        "id": str(item.id),
        "filename": item.filename,
        "file_size": item.file_size,
        "page_count": item.page_count,
        "status": item.status,
        "created_at": item.created_at.isoformat() if item.created_at else None,
    }
