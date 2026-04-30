import re
import logging
from typing import List

from pydantic import BaseModel

from app.schemas.edital_schema import Materia
from app.core.logging_streamer import log_streamer

logger = logging.getLogger(__name__)

_NUMBERING_PREFIX = re.compile(r"^\d+(\.\d+)*[\s\.\-\)]+")

_NOISE_TOPICO_PATTERNS: List[re.Pattern] = [
    re.compile(r"^p[áa]g\.?\s*\d+", re.IGNORECASE),
    re.compile(r"^(anexo|tabela|quadro)\s+[\divxlc]", re.IGNORECASE),
    re.compile(r"^(observa[çc][ãa]o|obs\.?|nota\s)", re.IGNORECASE),
    re.compile(r"[\s\.\-]{4,}"),  # long separator = PDF artifact
]


class SyllabusScore(BaseModel):
    total: int       # 0–10
    n_materias: int
    n_topicos: int
    verdict: str     # "elite" | "bom" | "revisar"


class SyllabusAuditorAgent:
    """Validação determinística e refinamento do Edital Verticalizado. Zero LLM, zero I/O."""

    def refine(self, materia: Materia) -> Materia:
        """Remove numerações de PDF e ruídos dos tópicos e nome da matéria."""
        nome = _NUMBERING_PREFIX.sub("", materia.nome.strip()).strip()
        cleaned = []
        for t in materia.topicos:
            t = _NUMBERING_PREFIX.sub("", t.strip()).strip()
            if not self._is_noise_topico(t) and len(t) > 3:
                cleaned.append(t)
        return Materia(nome=nome, topicos=cleaned, peso=materia.peso, quantidade_questoes=materia.quantidade_questoes)

    def audit(self, materias: List[Materia], anchor_text: str) -> SyllabusScore:
        """Score 0–10: penaliza extração rasa, recompensa cobertura e densidade."""
        anchor_text_len = len(anchor_text)
        n_materias = len(materias)
        n_topicos = sum(len(m.topicos) for m in materias)

        # Matérias (0–4): até 4 pontos para ≥ 4 matérias
        mat_score = min(4, n_materias)

        # Densidade (0–4): tópicos vs tamanho do contexto ancorado
        expected = max(5, anchor_text_len // 300)
        density_ratio = n_topicos / max(1, expected)
        top_score = min(4, int(density_ratio * 4))

        # Qualidade (0–2): penaliza matérias sem nenhum tópico
        empty = sum(1 for m in materias if not m.topicos)
        qual_score = 2 if empty == 0 else (1 if empty == 1 else 0)

        # Cobertura (0 a -2): penaliza matérias sem ancoragem semântica no texto
        if anchor_text:
            uncovered = sum(1 for m in materias if not self._check_coverage(m, anchor_text))
            cov_penalty = min(2, uncovered)
        else:
            cov_penalty = 0

        total = max(0, mat_score + top_score + qual_score - cov_penalty)
        verdict = "elite" if total >= 8 else ("bom" if total >= 5 else "revisar")

        icon = "💎" if verdict == "elite" else ("✅" if verdict == "bom" else "⚠️")
        log_streamer.broadcast({
            "type": "log",
            "message": (
                f"{icon} SyllabusAudit: score={total}/10 [{verdict}] "
                f"| {n_materias} matéria(s) | {n_topicos} tópico(s)"
                + (f" | cov_penalty=-{cov_penalty}" if cov_penalty else "")
            ),
            "level": "INFO",
        })
        logger.info(
            "SyllabusAuditor: score=%d/10 [%s] | %d matéria(s) | %d tópico(s) | %d vazia(s) | cov_penalty=%d",
            total, verdict, n_materias, n_topicos, empty, cov_penalty,
        )

        return SyllabusScore(total=total, n_materias=n_materias, n_topicos=n_topicos, verdict=verdict)

    def _check_coverage(self, materia: Materia, anchor_text: str) -> bool:
        """Verifica se o nome da matéria aparece semanticamente no texto âncora."""
        if not anchor_text:
            return True
        anchor = re.sub(r"[^a-z0-9]", "", anchor_text.lower())
        m_name = re.sub(r"[^a-z0-9]", "", materia.nome.lower())
        if len(m_name) < 10:
            return m_name in anchor
        words = [w for w in re.split(r"\s+", materia.nome.lower()) if len(w) > 4]
        if not words:
            return True
        found = sum(1 for w in words if re.sub(r"[^a-z0-9]", "", w) in anchor)
        return (found / len(words)) >= 0.6

    def _is_noise_topico(self, t: str) -> bool:
        return any(p.search(t) for p in _NOISE_TOPICO_PATTERNS)
