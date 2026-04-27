# Unified Docker Compose Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Unify all Docker Compose stacks (App, Jenkins, Sonar, Vault) into a single `docker-compose.all.yml` so that `make up` brings the entire ecosystem up on one shared network, fixing backend→db connectivity.

**Architecture:** Create `docker-compose.all.yml` using the Docker Compose `include:` top-level directive to merge all 4 existing compose files into a single project (`estudohub_40`). All services share the `estudohub_40_default` bridge network, so `backend` resolves `db` by service name. Existing volumes (`estudohub_40_postgres_data`, etc.) are reused — no data loss.

**Tech Stack:** Docker Compose v5.1.2 (supports `include` since v2.20), GNU Make

---

## File Map

| Action | File | Responsibility |
|--------|------|----------------|
| Create | `docker-compose.all.yml` | Include directive unifying all stacks |
| Modify | `Makefile` | Add `up`, `down`, `logs`, `ps`, `restart` targets |

---

### Task 1: Tear Down Existing Isolated Containers

Running containers (`estudohub_40-backend-1`, `jenkins`, `vault`) are on separate networks. They must be stopped before the unified stack can claim their ports and container names.

**Files:** none

- [ ] **Step 1.1: Stop the main app stack**

```bash
docker compose -f docker-compose.yml down
```

Expected output: containers `estudohub_40-backend-1` and `estudohub_40-ollama-1` stop and are removed.

- [ ] **Step 1.2: Stop Jenkins**

```bash
docker compose -f docker-compose.jenkins.yml down
```

Expected output: container `jenkins` stops and is removed.

- [ ] **Step 1.3: Stop Vault**

```bash
docker compose -f docker-compose.vault.yml down
```

Expected output: container `vault` stops and is removed.

- [ ] **Step 1.4: Verify all containers are stopped**

```bash
docker ps --format "table {{.Names}}\t{{.Status}}"
```

Expected output: empty table (no running containers).

---

### Task 2: Create `docker-compose.all.yml`

**Files:**
- Create: `docker-compose.all.yml`

- [ ] **Step 2.1: Create the file**

Create `/mnt/c/Dev/EstudoHub_4.0/docker-compose.all.yml` with exactly this content:

```yaml
include:
  - docker-compose.yml
  - docker-compose.jenkins.yml
  - docker-compose.sonar.yml
  - docker-compose.vault.yml
```

- [ ] **Step 2.2: Validate syntax**

```bash
docker compose -f docker-compose.all.yml config --quiet
```

Expected: no output, exit code 0. Any error indicates a syntax or include problem.

- [ ] **Step 2.3: Commit**

```bash
git add docker-compose.all.yml
git commit -m "feat(infra): add docker-compose.all.yml unifying all stacks via include"
```

---

### Task 3: Update Makefile

**Files:**
- Modify: `Makefile`

- [ ] **Step 3.1: Add unified targets to Makefile**

Add the following block at the **top** of the Makefile, before the existing `sonar-up` target. Also update the `.PHONY` line to include the new targets.

Replace the current `.PHONY` line:
```makefile
.PHONY: sonar-up sonar-down sonar-init sonar-scan test-backend
```

With:
```makefile
.PHONY: up down logs ps restart sonar-up sonar-down sonar-init sonar-scan test-backend vault-up vault-down vault-clean vault-init jenkins-up jenkins-down jenkins-logs jenkins-password
```

Then add this block immediately after the `.PHONY` line:
```makefile
COMPOSE_ALL := docker compose -f docker-compose.all.yml

up:
	$(COMPOSE_ALL) up -d

down:
	$(COMPOSE_ALL) down

logs:
	$(COMPOSE_ALL) logs -f

ps:
	$(COMPOSE_ALL) ps

restart:
	$(COMPOSE_ALL) restart

```

- [ ] **Step 3.2: Verify Makefile parses correctly**

```bash
make --dry-run up
```

Expected output:
```
docker compose -f docker-compose.all.yml up -d
```

- [ ] **Step 3.3: Commit**

```bash
git add Makefile
git commit -m "feat(infra): add make up/down/logs/ps/restart targeting docker-compose.all.yml"
```

---

### Task 4: Bring Up the Unified Stack

**Files:** none

- [ ] **Step 4.1: Start the full stack**

```bash
make up
```

Expected: Docker Compose pulls/builds images as needed and starts all services in detached mode. This may take a few minutes on first run (SonarQube is slow to start).

- [ ] **Step 4.2: Watch startup progress**

```bash
make logs
```

Watch for:
- `db` logging `database system is ready to accept connections`
- `backend` logging a successful startup (no `could not translate host name "db"` errors)
- Press `Ctrl+C` to stop following logs once the stack is stable.

- [ ] **Step 4.3: Check all containers are running**

```bash
make ps
```

Expected: all services listed with status `running` (except `sonar-scanner` which exits after scanning — `Exited (0)` or still waiting on SonarQube healthcheck is normal).

---

### Task 5: Validate Connectivity

**Files:** none

- [ ] **Step 5.1: Validate backend is reachable**

```bash
curl -s -o /dev/null -w "%{http_code}" http://localhost:8000/health || curl -s http://localhost:8000/
```

Expected: HTTP 200 (or the root API response). If the backend returns any response, it is up.

- [ ] **Step 5.2: Validate frontend is reachable**

```bash
curl -s -o /dev/null -w "%{http_code}" http://localhost:3000
```

Expected: HTTP 200.

- [ ] **Step 5.3: Validate backend→db connectivity via logs**

```bash
docker compose -f docker-compose.all.yml logs backend 2>&1 | grep -E "(error|Error|db|database|connect)" | tail -20
```

Expected: no lines containing `could not translate host name "db"`. Lines about successful DB connection or migration are a positive signal.

---

## Notes

- `sonar-scanner` is a run-once service that depends on SonarQube being healthy (90s start_period). It will show as `Exited (0)` after completing its scan — this is expected behavior.
- Individual Makefile targets (`sonar-up`, `vault-up`, `jenkins-up`, etc.) are preserved for isolated development use.
- Jenkins and Vault use named containers (`container_name: jenkins`, `container_name: vault`) — they must be fully stopped before the unified stack starts to avoid name conflicts.
- Existing data volumes (`estudohub_40_postgres_data`, `estudohub_40_ollama_data`, etc.) are automatically reused — no data is lost.
