import logging
import uuid
import json
from typing import List, Optional
from pydantic import BaseModel
from sqlalchemy.orm import Session

from app.db import models as db_models
from app.services.pdf_service import PDFService
from app.services.ai_service import AIService
from app.core.logging_streamer import log_streamer

logger = logging.getLogger(__name__)

class Flashcard(BaseModel):
    pergunta: str
    resposta: str

class TopicoIdentificado(BaseModel):
    materia: str
    topico: str
    resumo: str
    flashcards: List[Flashcard]

class LibraryService:
    """Serviço para gerenciar a Biblioteca e a extração de Tópicos Atômicos com Flashcards."""

    def __init__(self, ai_service: AIService):
        self.ai_service = ai_service

    async def process_document(self, db: Session, doc_id: uuid.UUID, file_path: str):
        """Pipeline: PDF -> Markdown -> Chunks -> IA Classification (Summary + Flashcards) -> Atomics."""
        try:
            doc = db.query(db_models.Documento).filter(db_models.Documento.id == doc_id).first()
            if not doc:
                return

            log_streamer.broadcast({"type": "log", "message": f"📚 Biblioteca: Iniciando processamento inteligente de {doc.filename}..."})
            
            # 1. Extração
            text = PDFService.to_markdown(file_path)
            if not text:
                raise ValueError("PDF ilegível ou vazio")

            # 2. Fragmentação (Chunks de ~4000 chars para dar mais contexto à IA)
            chunks = self._split_text(text, chunk_size=4000)
            log_streamer.broadcast({"type": "log", "message": f"📚 Biblioteca: Documento dividido em {len(chunks)} átomos de conhecimento."})

            # 3. Identificação por IA
            for i, chunk in enumerate(chunks):
                log_streamer.broadcast({"type": "log", "message": f"🤖 IA: Processando átomo {i+1}/{len(chunks)} (Identificação + Resumo + Flashcards)..."})
                identificacao = await self._identify_topic(chunk)
                
                if identificacao:
                    # 4. Persistência Atômica
                    atom = db_models.TopicoAtomico(
                        documento_id=doc.id,
                        materia=identificacao.materia,
                        topico=identificacao.topico,
                        original_text=chunk,
                        ai_summary=identificacao.resumo,
                        flashcards=json.dumps([f.model_dump() for f in identificacao.flashcards], ensure_ascii=False)
                    )
                    db.add(atom)
                    db.flush()
                    log_streamer.broadcast({
                        "type": "log", 
                        "message": f"✅ Átomo Processado: [{identificacao.materia}] {identificacao.topico} (+5 Flashcards)"
                    })

            doc.status = "concluido"
            db.commit()
            log_streamer.broadcast({"type": "log", "message": f"✨ Biblioteca: Inteligência gerada para {doc.filename}!"})

        except Exception as e:
            logger.error(f"Erro ao processar documento {doc_id}: {e}")
            if doc:
                doc.status = "erro"
                db.commit()
            log_streamer.broadcast({"type": "error", "message": f"❌ Erro na Inteligência da Biblioteca: {str(e)}"})

    def _split_text(self, text: str, chunk_size: int) -> List[str]:
        """Divide o texto em pedaços respeitando quebras de linha."""
        chunks = []
        current_chunk = []
        current_length = 0
        
        for line in text.splitlines():
            if current_length + len(line) > chunk_size and current_chunk:
                chunks.append("\n".join(current_chunk))
                current_chunk = []
                current_length = 0
            current_chunk.append(line)
            current_length += len(line)
            
        if current_chunk:
            chunks.append("\n".join(current_chunk))
        return chunks

    async def _identify_topic(self, chunk: str) -> Optional[TopicoIdentificado]:
        """Usa o Ollama (via AIService chain) para gerar a inteligência do trecho."""
        prompt = f"""
        Você é um Especialista em Pedagogia e Concursos Públicos. 
        Analise o trecho de material de estudo abaixo e gere a inteligência atômica.
        
        SUA MISSÃO:
        1. IDENTIFICAÇÃO: Determine a Matéria (ex: Direito Administrativo) e o Tópico (ex: Atos Administrativos).
        2. RESUMO ATÔMICO: Crie um resumo técnico de alto nível, focado em conceitos-chave e pegadinhas comuns.
        3. FLASHCARDS: Gere exatamente 5 perguntas e respostas curtas e diretas para memorização ativa.

        REGRAS DE RESPOSTA:
        - Retorne APENAS um JSON puro.
        - Não adicione explicações fora do JSON.
        
        FORMATO JSON:
        {{
            "materia": "string",
            "topico": "string",
            "resumo": "string",
            "flashcards": [
                {{"pergunta": "string", "resposta": "string"}},
                {{"pergunta": "string", "resposta": "string"}},
                {{"pergunta": "string", "resposta": "string"}},
                {{"pergunta": "string", "resposta": "string"}},
                {{"pergunta": "string", "resposta": "string"}}
            ]
        }}

        TEXTO PARA ANÁLISE:
        {chunk}
        """
        
        chain = self.ai_service._get_provider_chain()
        for provider in chain:
            try:
                # O provider Ollama (ou outros na chain) cuidará da chamada
                result = await provider.generate_json(prompt=prompt, schema=TopicoIdentificado)
                return result
            except Exception as e:
                logger.warning(f"Provider {provider.__class__.__name__} falhou na geração atômica: {e}")
                continue
        return None
