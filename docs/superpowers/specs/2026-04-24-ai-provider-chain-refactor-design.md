# AI Provider Chain Refactor — Design Spec
**Date:** 2026-04-24  
**Status:** Approved

## Problem

The EstudoHub 4.0 backend has a fallback chain defined in `AIService._get_provider_chain()` that is never executed. The actual pipeline in `endpoints.py` calls `CargoTitleAgent`, `CargoVitaminizerAgent`, and `SubjectsScoutAgent` directly — each with a hardcoded two-provider list (`[ollama, gemini]`). When Ollama fails (wrong URL: `localhost` instead of `ollama`) and Gemini hits its free-tier quota (429), the pipeline produces zero AI output with no further retries.

## Goals

1. Ollama runs as a first-class Docker service — always tried first, always reachable.
2. A single provider chain (`Ollama → Groq → NVIDIA → OpenRouter → Gemini`) is built in one place and injected into every agent.
3. `AIService` becomes the pipeline orchestrator; `endpoints.py` is thin.
4. Provider failures are silent (WARNING log) and never block processing.

## Out of Scope

- Adding new agents or AI capabilities.
- Changing the subtractive pipeline (GeometricEngine, SubtractiveAgent).
- UI / frontend changes.

---

## Architecture

### Approach: C1 — Dependency Injection

`AIService` builds the chain and injects it into each agent call. Agents keep their domain logic but receive `chain: List[BaseLLMProvider]` as a parameter instead of constructing their own providers internally.

```
endpoints.py
    └── _process_edital_task()
            └── AIService.process_edital(content_hash, md_content)
                    ├── _get_provider_chain()  →  [Ollama, Groq, NVIDIA, OpenRouter, Gemini]
                    ├── CargoTitleAgent.hunt_titles(content_hash, chain)
                    ├── CargoVitaminizerAgent.vitaminize(content_hash, cargos, chain)
                    └── SubjectsScoutAgent.scout(content_hash, cargos_vitaminados, chain)
```

---

## Component Changes

### 1. `docker-compose.yml`

Add `ollama` service:

```yaml
ollama:
  image: ollama/ollama
  volumes:
    - ollama_data:/root/.ollama
  ports:
    - "11434:11434"
```

- `backend.depends_on` gains `ollama`.
- Volume `ollama_data` added to top-level `volumes`.
- Model pulled via `docker exec ollama ollama pull llama3.1:8b` on first run (or via entrypoint script).

### 2. `backend/.env`

```
OLLAMA_URL=http://ollama:11434
```

Replaces the broken `http://localhost:11434`.

### 3. `ai_service.py` — `_get_provider_chain()`

New order, Ollama always first regardless of `llm_strategy`:

```
[OllamaProvider] always
+ [GroqProvider]       if settings.groq_api_key
+ [NVIDIAProvider]     if settings.nvidia_api_key
+ [OpenRouterProvider] if settings.openrouter_api_key
+ [GeminiProvider]     if settings.gemini_api_key
```

If no cloud key is configured, chain is `[Ollama]` only — no silent empty chain.

### 4. `ai_service.py` — new `process_edital()` method

Replaces the pipeline logic currently in `endpoints._process_edital_task()`:

```python
async def process_edital(self, content_hash: str, md_content: str) -> dict:
    chain = self._get_provider_chain()
    cargos = await self.cargo_agent.hunt_titles(content_hash, chain)
    vitamin_data = await self.vitaminizer_agent.vitaminize(content_hash, cargos, chain)
    cargos_com_materias = await self.subjects_scout_agent.scout(
        content_hash, vitamin_data.cargos_vitaminados, chain
    )
    return {"edital": vitamin_data.edital_info, "cargos": cargos_com_materias}
```

`AIService.__init__` gains instances of the three agents.

### 5. `cargo_specialist.py` — `CargoTitleAgent`

- `hunt_titles(content_hash, chain)` — adds `chain` parameter, passes to `_deep_scan`.
- `_deep_scan(fragment, chain)` — replaces hardcoded `providers = [ollama, gemini]` with the injected `chain`. Loop with `try/except Exception → WARNING log → continue`.

### 6. `cargo_vitaminizer.py` — `CargoVitaminizerAgent`

- `vitaminize(content_hash, identified_cargos, chain)` — adds `chain` parameter.
- `_discover_structure(main_md, tables, chain)` — replaces single-provider pick with chain loop.
- `_extract_global_metadata(main_md, chain)` — same.

### 7. `subjects_scout.py` — `SubjectsScoutAgent`

- `scout(content_hash, cargos, chain)` — adds `chain` parameter, passes to internal AI calls.
- All internal AI calls replaced with chain loop.

### 8. `endpoints.py`

- Import `AIService`.
- `_process_edital_task()` replaces the direct agent calls with:
  ```python
  ai_service = AIService()
  result = await ai_service.process_edital(content_hash, md_content)
  ```
- Direct instantiation of `cargo_agent`, `vitaminizer_agent`, `subjects_scout_agent` at module level removed.

---

## Error Handling

Every provider failure inside a chain loop:
- Logs `WARNING: ⚠️ <ProviderName> falhou, tentando próximo: <error>`
- Does NOT raise — `continue` to next provider.
- If all providers fail, returns empty result (current behavior) and logs `ERROR: Todos os providers falharam`.

No retries per provider — fail fast and move to next.

---

## Testing

- Unit: mock chain with two providers — first raises, second returns valid result. Assert second is used.
- Integration: upload a sample edital with only Ollama configured — confirm processing completes.
- Smoke: `curl http://localhost:8000/health` returns `{"status": "healthy"}` after `docker compose up`.

---

## Risks

| Risk | Mitigation |
|------|-----------|
| Ollama model not pulled on fresh start | Document `docker exec ollama ollama pull llama3.1:8b` in README; consider init container |
| Groq/NVIDIA/OpenRouter keys absent → chain is Ollama-only | Acceptable — Ollama is priority #1; log WARNING at startup if no cloud keys found |
| Circular imports (AIService ↔ agents) | AIService imports agents; agents import only providers — no circular dependency |
