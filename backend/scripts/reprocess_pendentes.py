import asyncio
import logging
from app.db.database import SessionLocal
from app.db import models
from app.services.ai_service import AIService
from app.schemas.edital_schema import CargoIdentificado

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

async def reprocess_pendentes():
    service = AIService()
    db = SessionLocal()
    
    try:
        # Busca editais com Órgão Pendente
        pendentes = db.query(models.Edital).filter(models.Edital.orgao == "Pendente").all()
        logger.info(f"Encontrados {len(pendentes)} editais com Órgão Pendente.")
        
        for edital in pendentes:
            logger.info(f"Reprocessando edital ID {edital.id} (Hash: {edital.content_hash})...")
            
            # Carrega cargos identificados para este edital para passar para o vitaminizer
            # (O Vitaminizer precisa dos cargos para fazer a soma de vagas)
            cargos_db = db.query(models.Cargo).filter(models.Cargo.edital_id == edital.id).all()
            identified_cargos = [CargoIdentificado(titulo=c.titulo, codigo_edital=c.codigo_edital) for c in cargos_db]
            
            # Executa a Vitaminização (agora com o prompt corrigido e Fallback Gemini)
            # VitaminizerAgent.vitaminize(content_hash, identified_cargos, chain)
            chain = service._get_provider_chain()
            vitamin_data = await service.vitaminizer_agent.vitaminize(edital.content_hash, identified_cargos, chain)
            
            new_info = vitamin_data.edital_info
            
            if new_info.orgao != "Pendente":
                logger.info(f"✅ Sucesso! Novo Órgão: {new_info.orgao} | Banca: {new_info.banca}")
                edital.orgao = new_info.orgao
                edital.banca = new_info.banca
                if new_info.data_prova and new_info.data_prova != "Pendente":
                    edital.data_prova = new_info.data_prova
                db.commit()
            else:
                logger.warning(f"⚠️ Ainda Pendente para {edital.content_hash}. Tentando novamente no próximo ciclo.")

    finally:
        db.close()

if __name__ == "__main__":
    asyncio.run(reprocess_pendentes())
