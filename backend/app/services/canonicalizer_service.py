import logging
from typing import Optional, List, Tuple
from sqlalchemy.orm import Session
from sqlalchemy import select

from app.db.models import CanonicalTopic
from app.providers.gemini_provider import GeminiProvider

logger = logging.getLogger(__name__)

class CanonicalizerService:
    """Serviço para canonização de tópicos de editais via embeddings."""

    def __init__(self, db: Session, gemini_provider: Optional[GeminiProvider] = None):
        self.db = db
        self.gemini_provider = gemini_provider or GeminiProvider()

    async def canonicalize(self, topic_name: str, threshold: float = 0.8) -> Tuple[Optional[CanonicalTopic], float]:
        """
        Recebe um tópico, gera o embedding e busca o vizinho mais próximo.
        Retorna o tópico canonizado e a pontuação de similaridade (distância de cosseno invertida).
        """
        logger.info(f"Canonicalizing topic: {topic_name}")
        
        try:
            # 1. Gerar embedding do tópico recebido
            embedding = await self.gemini_provider.embed_text(topic_name)
            
            # 2. Buscar no banco usando pgvector (distância de cosseno)
            # No pgvector, <=> é a distância de cosseno. 1 - distância = similaridade.
            stmt = select(
                CanonicalTopic, 
                (1 - CanonicalTopic.embedding.cosine_distance(embedding)).label("similarity")
            ).order_by(
                CanonicalTopic.embedding.cosine_distance(embedding)
            ).limit(1)
            
            result = self.db.execute(stmt).first()
            
            if result:
                topic, similarity = result
                if similarity >= threshold:
                    logger.info(f"Match found: {topic.name} (Sim: {similarity:.4f})")
                    return topic, similarity
                else:
                    logger.info(f"No match above threshold {threshold} (Best: {similarity:.4f})")
            
            return None, 0.0
            
        except Exception as e:
            logger.error(f"Error during canonicalization: {e}")
            return None, 0.0

    async def add_canonical_topic(self, name: str, area: Optional[str] = None) -> CanonicalTopic:
        """Adiciona um novo tópico canônico ao banco."""
        embedding = await self.gemini_provider.embed_text(name)
        
        new_topic = CanonicalTopic(
            name=name,
            area=area,
            embedding=embedding
        )
        
        self.db.add(new_topic)
        self.db.commit()
        self.db.refresh(new_topic)
        
        logger.info(f"Added new canonical topic: {name}")
        return new_topic
