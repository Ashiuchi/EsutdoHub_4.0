import logging
from typing import List, Optional, Tuple
from sqlalchemy.orm import Session
from sqlalchemy import select

from app.db.models import CanonicalTopic
from app.providers.ollama_provider import OllamaProvider

logger = logging.getLogger(__name__)


class CanonicalizerService:
    """Serviço para canonização de tópicos de editais via embeddings locais."""

    def __init__(self, db: Session, ai_provider: Optional[OllamaProvider] = None):
        self.db = db
        self.ai_provider = ai_provider or OllamaProvider()

    async def canonicalize(
        self,
        topic_name: str,
        threshold: float = 0.65,
        embedding: Optional[List[float]] = None,
    ) -> Tuple[Optional[CanonicalTopic], float]:
        """Busca o tópico canônico mais próximo via pgvector.

        Aceita um embedding pré-computado para evitar chamada extra à API quando
        o chamador já gerou o vetor (ex: pipeline de enriquecimento).
        """
        try:
            if embedding is None:
                embedding = await self.ai_provider.embed_text(topic_name)

            stmt = (
                select(
                    CanonicalTopic,
                    (1 - CanonicalTopic.embedding.cosine_distance(embedding)).label("similarity"),
                )
                .order_by(CanonicalTopic.embedding.cosine_distance(embedding))
                .limit(1)
            )

            result = self.db.execute(stmt).first()
            if result:
                topic, similarity = result
                if similarity >= threshold:
                    logger.debug("Match: %s (sim=%.4f)", topic.name, similarity)
                    return topic, similarity
                logger.debug("No match above %.2f (best=%.4f)", threshold, similarity)

            return None, 0.0

        except Exception as exc:
            logger.error("Canonicalization error for '%s': %s", topic_name[:60], exc)
            return None, 0.0

    async def add_canonical_topic(self, name: str, area: Optional[str] = None) -> CanonicalTopic:
        """Adiciona um novo tópico canônico ao banco."""
        embedding = await self.ai_provider.embed_text(name)
        
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
