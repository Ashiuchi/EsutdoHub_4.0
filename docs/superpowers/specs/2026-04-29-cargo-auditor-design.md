# CargoAuditorAgent — Design Spec
**Date:** 2026-04-29

## Objetivo
Camada de qualidade após o `CargoVitaminizerAgent`. Cada cargo passa por um "Raio-X" que: (1) descarta ruído estrutural do edital, (2) pontua a completude dos dados e (3) roteia o cargo para aprovação, quarentena ou descarte.

## Regras de Routing

| Condição | Destino |
|---|---|
| `is_noise = True` | 🗑️ Descartado — não persiste no banco |
| `score < 6` | ⚠️ `status = "quarentena"` — persiste, visível no Cockpit, não vai ao SubjectsScout |
| `score >= 6` | ✅ `status = "vitaminado"` — persiste, segue para o SubjectsScout |

## Modelos

```python
class AuditDimensions(BaseModel):
    salario: int      # 0–3
    escolaridade: int # 0–3
    vagas: int        # 0–2
    detalhes: int     # 0–2

class AuditResult(BaseModel):
    cargo: Cargo
    score: int        # 0–10
    is_noise: bool
    dimensions: AuditDimensions
    verdict: str      # "aprovado" | "quarentena"
```

## Scoring

| Dimensão | Peso | Regra |
|---|---|---|
| `salario` | 3 | `3` se `salario > 0.0`, senão `0` |
| `escolaridade` | 3 | `3` se não for `"Não informada"` / `"Pendente"`, senão `0` |
| `vagas` | 2 | `2` se `vagas_total > 0`; `1` se alguma vaga parcial > 0; `0` se tudo zero |
| `detalhes` | 2 | `2` se ≥ 2 de {atribuicoes, requisitos, jornada} preenchidos; `1` se 1; `0` se nenhum |

Limiar de quarentena: `score < 6`.

## Filtro de Ruído (regex, case-insensitive)

```
^anexo\s*[\divxlc]        → "Anexo II", "Anexo 3"
^tabela\s*\d              → "Tabela 1"
^quadro\s*[\divxlc]       → "Quadro I"
taxa[s]?\s+de             → "Taxas de Inscrição"
^\d+[\.\-]\s*\w           → "1. Cargo X"
^(total|subtotal)$        → artefato de tabela
^(observa[çc]|obs\.?)     → "Observação"
^nota\s                   → "Nota 1"
```

## Arquitetura

**Novo arquivo:** `backend/app/services/cargo_auditor.py`
- Classe pura — sem LLM, sem I/O, sem semáforo
- Interface pública: `audit(cargos: List[Cargo]) -> List[AuditResult]`
- Internos: `_is_noise(titulo)`, `_score_dimensions(cargo)`

## Integração na AIService

```
CargoVitaminizerAgent.vitaminize()
        ↓
CargoAuditorAgent.audit()
        ├── is_noise → descartado
        ├── score < 6 → quarentena (persiste, skip Scout)
        └── score >= 6 → SubjectsScoutAgent.scout() → persiste
```

`self.cargo_auditor = CargoAuditorAgent()` no `__init__` da AIService.

## Arquivos a Criar/Modificar

| Arquivo | Ação |
|---|---|
| `backend/app/services/cargo_auditor.py` | Criar |
| `backend/tests/services/test_cargo_auditor.py` | Criar |
| `backend/app/services/ai_service.py` | Modificar — inserir auditor após vitaminize |
