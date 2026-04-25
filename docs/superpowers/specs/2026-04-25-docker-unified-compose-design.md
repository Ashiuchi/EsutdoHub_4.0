# Design: Unified Docker Compose — EstudoHub Pro 4.0

**Date:** 2026-04-25  
**Status:** Approved

## Problem

Services run as isolated Docker projects (islands). The `backend` container cannot resolve the `db` hostname because each compose file creates its own bridge network. Running `docker compose -f docker-compose.yml up -d` brings up `backend` but `db` may be down or on a different network, causing connection failures.

## Solution: `include` Directive

Create `docker-compose.all.yml` at project root using Docker Compose's `include:` top-level element (available since Compose v2.20, current env has v5.1.2).

## Architecture

```
docker-compose.all.yml
  └── include:
        ├── docker-compose.yml          → db, backend, frontend, cache, ollama
        ├── docker-compose.jenkins.yml  → jenkins
        ├── docker-compose.sonar.yml    → sonarqube, sonar-scanner
        └── docker-compose.vault.yml    → vault

Resulting network: estudohub_40_default (shared by all services)
  backend ──→ db         ✅
  backend ──→ cache      ✅
  backend ──→ ollama     ✅
  jenkins ──→ host       ✅
```

All services merge into project `estudohub_40`. Existing volumes (`estudohub_40_postgres_data`, `estudohub_40_ollama_data`, etc.) are preserved — no data loss.

## Files Changed

| File | Action |
|------|--------|
| `docker-compose.all.yml` | Create — include directive unifying all 4 compose files |
| `Makefile` | Add `up`, `down`, `logs`, `ps`, `restart` targets using the unified file |

Existing compose files and their individual Makefile targets are **unchanged** — still usable for isolated development.

## Validation

1. `docker compose -f docker-compose.all.yml ps` — all services listed
2. `curl -s http://localhost:8000/health` — backend responds
3. `curl -s http://localhost:3000` — frontend responds
4. Backend logs show no `db` hostname resolution errors

## Out of Scope

- Changes to individual compose files
- Vault initialization / Jenkins setup
- CI/CD pipeline changes
