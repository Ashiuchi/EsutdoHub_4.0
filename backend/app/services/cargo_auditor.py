import re
import logging
from typing import List, Optional

from pydantic import BaseModel

from app.schemas.edital_schema import Cargo
from app.core.logging_streamer import log_streamer

logger = logging.getLogger(__name__)

_SENTINEL = {"Não informada", "não informada", "Pendente", "pendente", "", None}

_NOISE_PATTERNS: List[re.Pattern] = [
    re.compile(r"^anexo\s*[\divxlcIVXLC]", re.IGNORECASE),
    re.compile(r"^tabela\s*\d", re.IGNORECASE),
    re.compile(r"^quadro\s*[\divxlcIVXLC]", re.IGNORECASE),
    re.compile(r"taxa[s]?\s+de", re.IGNORECASE),
    re.compile(r"^\d+[\.\-]\s*\w", re.IGNORECASE),
    re.compile(r"^(total|subtotal)$", re.IGNORECASE),
    re.compile(r"^(observa[çc][aã]o|obs\.?)", re.IGNORECASE),
    re.compile(r"^nota\s", re.IGNORECASE),
    re.compile(r"(comiss[ãa]o|membro[s]?|presidente|secret[áa]rio|coordenador)", re.IGNORECASE),
    re.compile(r"^(doutorado|mestrado|especializa[çc][ãa]o|p[óo]s-gradua[çc][ãa]o)$", re.IGNORECASE),
    re.compile(r"^(ensino\s+(m[ée]dio|superior|fundamental)|n[íi]vel\s+(m[ée]dio|superior|fundamental))$", re.IGNORECASE),
    re.compile(r"^(requisito|atribui[çc][ãa]o|jornada|sal[áa]rio|vagas)$", re.IGNORECASE),
]


class AuditDimensions(BaseModel):
    salario: int      # 0–3
    escolaridade: int # 0–3
    vagas: int        # 0–2
    detalhes: int     # 0–2


class AuditResult(BaseModel):
    cargo: Cargo
    score: int
    is_noise: bool
    dimensions: AuditDimensions
    verdict: str  # "aprovado" | "quarentena"


class CargoAuditorAgent:
    """Raio-X de qualidade pós-vitaminização. Zero LLM, zero I/O."""

    def audit(self, cargos: List[Cargo]) -> List[AuditResult]:
        results = []
        for cargo in cargos:
            noise = self._is_noise(cargo.titulo)
            dims = self._score_dimensions(cargo)
            score = dims.salario + dims.escolaridade + dims.vagas + dims.detalhes
            verdict = "aprovado" if score >= 6 else "quarentena"

            if noise:
                log_streamer.broadcast({
                    "type": "log",
                    "message": f"🗑️ Ruído descartado: '{cargo.titulo}'",
                    "level": "INFO",
                })
            else:
                icon = "✅" if verdict == "aprovado" else "⚠️"
                log_streamer.broadcast({
                    "type": "log",
                    "message": (
                        f"{icon} Auditoria '{cargo.titulo}': "
                        f"score={score}/10 "
                        f"[sal={dims.salario} esc={dims.escolaridade} "
                        f"vag={dims.vagas} det={dims.detalhes}]"
                    ),
                    "level": "INFO",
                })

            results.append(AuditResult(
                cargo=cargo,
                score=score,
                is_noise=noise,
                dimensions=dims,
                verdict=verdict,
            ))

        approved = sum(1 for r in results if not r.is_noise and r.verdict == "aprovado")
        quarantined = sum(1 for r in results if not r.is_noise and r.verdict == "quarentena")
        discarded = sum(1 for r in results if r.is_noise)
        logger.info(
            "CargoAuditor: %d aprovado(s), %d quarentena, %d ruído descartado.",
            approved, quarantined, discarded,
        )
        return results

    def _is_noise(self, titulo: str) -> bool:
        t = (titulo or "").strip()
        return any(p.search(t) for p in _NOISE_PATTERNS)

    def _score_dimensions(self, cargo: Cargo) -> AuditDimensions:
        return AuditDimensions(
            salario=self._score_salario(cargo.salario),
            escolaridade=self._score_escolaridade(cargo.escolaridade),
            vagas=self._score_vagas(cargo),
            detalhes=self._score_detalhes(cargo),
        )

    @staticmethod
    def _score_salario(salario: Optional[float]) -> int:
        return 3 if salario and salario > 0.0 else 0

    @staticmethod
    def _score_escolaridade(escolaridade: Optional[str]) -> int:
        return 3 if escolaridade not in _SENTINEL else 0

    @staticmethod
    def _score_vagas(cargo: Cargo) -> int:
        def _int(v: Optional[str]) -> int:
            try:
                return int(v or 0)
            except (ValueError, TypeError):
                return 0

        if _int(cargo.vagas_total) > 0:
            return 2
        partials = [cargo.vagas_ac, cargo.vagas_pcd, cargo.vagas_cr,
                    cargo.vagas_negros, cargo.vagas_indigenas, cargo.vagas_trans]
        if any(_int(v) > 0 for v in partials):
            return 1
        return 0

    @staticmethod
    def _score_detalhes(cargo: Cargo) -> int:
        fields = [cargo.atribuicoes, cargo.requisitos, cargo.jornada]
        filled = sum(1 for f in fields if f not in _SENTINEL)
        if filled >= 2:
            return 2
        if filled == 1:
            return 1
        return 0
