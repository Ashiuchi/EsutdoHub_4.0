import os
import uuid
import hashlib
import logging
import aiofiles
from fastapi import APIRouter, UploadFile, File, Depends, BackgroundTasks, HTTPException
from sqlalchemy.orm import Session

from app.db.database import SessionLocal
from app.db import models as db_models
from app.services.ai_service import AIService
from app.services.library_service import LibraryService
from app.core.auth import verify_clerk_token

router = APIRouter()
logger = logging.getLogger(__name__)

# Dependência do DB
def get_db():
    db = SessionLocal()
    try:
        yield db
    finally:
        db.close()

# Inicialização de Serviços
ai_service = AIService()
library_service = LibraryService(ai_service)

STORAGE_PATH = "backend/storage/library"
os.makedirs(STORAGE_PATH, exist_ok=True)

def _compute_hash(file_bytes: bytes) -> str:
    return hashlib.sha256(file_bytes).hexdigest()

@router.post("/upload")
async def upload_documento(
    background_tasks: BackgroundTasks,
    file: UploadFile = File(...),
    db: Session = Depends(get_db),
    payload: dict = Depends(verify_clerk_token)
):
    """Upload de material para a Biblioteca Atômica."""
    user_id = payload.get("sub")
    if not user_id:
        raise HTTPException(status_code=401, detail="Usuário não identificado")

    file_bytes = await file.read()
    content_hash = _compute_hash(file_bytes)

    # 1. Verificar duplicata
    existing = db.query(db_models.Documento).filter(db_models.Documento.content_hash == content_hash).first()
    if existing:
        return {"id": existing.id, "status": existing.status, "message": "Arquivo já processado."}

    # 2. Salvar arquivo físico
    file_ext = os.path.splitext(file.filename)[1]
    safe_filename = f"{content_hash}{file_ext}"
    full_path = os.path.join(STORAGE_PATH, safe_filename)
    
    async with aiofiles.open(full_path, "wb") as buffer:
        await buffer.write(file_bytes)

    # 3. Criar registro no banco
    doc = db_models.Documento(
        user_id=user_id,
        filename=file.filename,
        file_path=full_path,
        content_hash=content_hash,
        status="processando"
    )
    db.add(doc)
    db.commit()
    db.refresh(doc)

    # 4. Disparar processamento atômico em background
    background_tasks.add_task(library_service.process_document, db, doc.id, full_path)

    return {
        "id": doc.id,
        "filename": doc.filename,
        "status": doc.status,
        "message": "Upload concluído. Processamento atômico iniciado."
    }

@router.get("/")
async def list_documentos(
    db: Session = Depends(get_db),
    payload: dict = Depends(verify_clerk_token)
):
    """Lista documentos da biblioteca do usuário."""
    user_id = payload.get("sub")
    docs = db.query(db_models.Documento).filter(db_models.Documento.user_id == user_id).all()
    return docs

@router.get("/{doc_id}/atomos")
async def get_atomos(
    doc_id: uuid.UUID,
    db: Session = Depends(get_db),
    payload: dict = Depends(verify_clerk_token)
):
    """Retorna os tópicos atômicos extraídos de um documento."""
    user_id = payload.get("sub")
    doc = db.query(db_models.Documento).filter(db_models.Documento.id == doc_id, db_models.Documento.user_id == user_id).first()
    if not doc:
        raise HTTPException(status_code=404, detail="Documento não encontrado")
    
    return doc.topicos_atomicos
