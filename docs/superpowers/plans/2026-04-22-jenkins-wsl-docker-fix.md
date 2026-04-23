# Jenkins WSL/Docker Fix Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Make Jenkins run reliably inside Docker on WSL, eliminating volume mapping errors and missing-tool failures, with full test and SonarQube integration.

**Architecture:** Jenkins container mounts the project dir to the exact WSL path `/mnt/d/DevOps/EstudoHub_4.0`, uses that path as its workspace, and delegates all work (tests, scans) to Docker via the host socket. A reset script provides a clean rebuild entry-point.

**Tech Stack:** Jenkins LTS, Docker-in-Docker (socket mount), docker-compose-plugin, SonarQube Community, pytest + coverage, Makefile, bash.

---

## File Map

| File | Action | Responsibility |
|------|--------|----------------|
| `Dockerfile.jenkins` | Modify | Add `docker-compose-plugin` and `curl` runtime install |
| `docker-compose.jenkins.yml` | Modify | Add `extra_hosts` for host resolution; confirm volume/workdir |
| `Jenkinsfile` | Modify | `customWorkspace`, fixed test command, SonarQube with correct URL |
| `scripts/jenkins_reset.sh` | Create | Stop, prune, rebuild, start Jenkins cleanly |

---

### Task 1: Fix Dockerfile.jenkins — add docker-compose-plugin

**Files:**
- Modify: `Dockerfile.jenkins`

**Problem:** `docker compose` subcommand (V2 plugin) is not installed; only the old `docker-compose` standalone CLI (not installed at all) or raw `docker-ce-cli`. The pipeline fails when it calls `docker compose version`.

- [ ] **Step 1: Replace the RUN block in Dockerfile.jenkins**

Open `Dockerfile.jenkins`. Replace the entire `RUN apt-get update ...` block with:

```dockerfile
FROM jenkins/jenkins:lts
USER root

RUN apt-get update && \
    apt-get install -y \
        apt-transport-https \
        ca-certificates \
        curl \
        gnupg \
        lsb-release \
        make && \
    curl -fsSL https://download.docker.com/linux/debian/gpg \
        | gpg --dearmor -o /usr/share/keyrings/docker-archive-keyring.gpg && \
    echo "deb [arch=$(dpkg --print-architecture) signed-by=/usr/share/keyrings/docker-archive-keyring.gpg] \
        https://download.docker.com/linux/debian $(lsb_release -cs) stable" \
        > /etc/apt/sources.list.d/docker.list && \
    apt-get update && \
    apt-get install -y docker-ce-cli docker-compose-plugin && \
    rm -rf /var/lib/apt/lists/*

USER jenkins
```

Key additions: `docker-compose-plugin` (enables `docker compose` V2 subcommand), `make`, `curl` all in the same layer.

- [ ] **Step 2: Verify the file looks correct**

```bash
cat Dockerfile.jenkins
```

Expected output: `docker-ce-cli docker-compose-plugin` on the same `apt-get install -y` line.

- [ ] **Step 3: Commit**

```bash
git add Dockerfile.jenkins
git commit -m "fix(jenkins): install docker-compose-plugin and make in Dockerfile"
```

---

### Task 2: Fix docker-compose.jenkins.yml — add extra_hosts

**Files:**
- Modify: `docker-compose.jenkins.yml`

**Problem:** From inside the Jenkins container, `host.docker.internal` must resolve to the host machine (needed for Vault health-check and any host-side services). On Linux/WSL the host gateway isn't auto-mapped the way it is on Mac/Windows Docker Desktop.

- [ ] **Step 1: Add extra_hosts to the jenkins service**

Open `docker-compose.jenkins.yml`. Under the `jenkins:` service, after `working_dir`, add:

```yaml
    extra_hosts:
      - "host.docker.internal:host-gateway"
```

Final file should look like:

```yaml
services:
  jenkins:
    build:
      context: .
      dockerfile: Dockerfile.jenkins
    container_name: jenkins
    restart: always
    user: root
    ports:
      - "8085:8080"
      - "50000:50000"
    volumes:
      - jenkins_data:/var/jenkins_home
      - /var/run/docker.sock:/var/run/docker.sock
      - .:/mnt/d/DevOps/EstudoHub_4.0
    working_dir: /mnt/d/DevOps/EstudoHub_4.0
    extra_hosts:
      - "host.docker.internal:host-gateway"
    environment:
      - TZ=America/Sao_Paulo

volumes:
  jenkins_data:
```

- [ ] **Step 2: Commit**

```bash
git add docker-compose.jenkins.yml
git commit -m "fix(jenkins): add host.docker.internal resolution for WSL"
```

---

### Task 3: Rewrite Jenkinsfile — customWorkspace, fixed test and SonarQube commands

**Files:**
- Modify: `Jenkinsfile`

**Problems:**
1. `agent any` makes Jenkins check out to a random workspace under `/var/jenkins_home/workspace/...`, ignoring the mounted project dir.
2. `dir("${PROJECT_DIR}")` works around the wrong workspace but is fragile.
3. Pytest coverage XML path `/usr/src/backend/test-reports/coverage.xml` doesn't match the backend container's layout (`/app`).
4. `VAULT_ADDR = "http://localhost:8205"` — `localhost` inside the Jenkins container means the container itself, not the host. Should be `host.docker.internal`.

- [ ] **Step 1: Replace Jenkinsfile entirely**

```groovy
pipeline {
    agent {
        node {
            customWorkspace '/mnt/d/DevOps/EstudoHub_4.0'
        }
    }

    environment {
        VAULT_ADDR  = "http://host.docker.internal:8205"
        PROJECT_DIR = "/mnt/d/DevOps/EstudoHub_4.0"
    }

    stages {
        stage('Prepare') {
            steps {
                echo 'Checking Environment...'
                sh 'docker --version'
                sh 'docker compose version'
                sh 'make --version'
            }
        }

        stage('Tests & Coverage') {
            steps {
                echo 'Running Backend Tests inside Docker Container...'
                sh 'mkdir -p backend/test-reports'
                sh '''docker compose run --rm backend \
                    pytest tests \
                    --cov=app \
                    --cov-report=xml:test-reports/coverage.xml \
                    --cov-report=term-missing'''
            }
        }

        stage('SonarQube Analysis') {
            steps {
                echo 'Running SonarQube Scan...'
                sh 'make sonar-scan'
            }
        }

        stage('Security Check') {
            steps {
                echo 'Verifying Vault Status...'
                sh '''curl -s -f http://host.docker.internal:8205/v1/sys/health \
                    || echo "Vault health check failed but proceeding..."'''
            }
        }
    }

    post {
        always {
            echo 'Cleaning up temporary files...'
            sh 'find . -name "*.pyc" -delete'
            sh 'find . -name "__pycache__" -type d -exec rm -rf {} +'
        }
        success {
            echo 'Pipeline completed successfully!'
        }
        failure {
            echo 'Pipeline failed. Check the logs above.'
        }
    }
}
```

Key changes:
- `agent { node { customWorkspace '/mnt/d/DevOps/EstudoHub_4.0' } }` — Jenkins uses the mounted project dir directly.
- `VAULT_ADDR` points to `host.docker.internal` instead of `localhost`.
- `mkdir -p backend/test-reports` before pytest to avoid "no such file" errors.
- pytest coverage output is `test-reports/coverage.xml` (relative to `/app` inside the backend container, which maps to `backend/test-reports/coverage.xml` on the host).
- `dir()` blocks removed — workspace is already correct.
- Vault health check uses only `host.docker.internal`; redundant fallback to `localhost` removed (it was always wrong inside the container).

- [ ] **Step 2: Verify the file**

```bash
cat Jenkinsfile
```

Confirm: first line of `agent {}` block is `node {`, and `customWorkspace '/mnt/d/DevOps/EstudoHub_4.0'` is present.

- [ ] **Step 3: Commit**

```bash
git add Jenkinsfile
git commit -m "fix(jenkins): use customWorkspace and correct test/vault commands"
```

---

### Task 4: Create scripts/jenkins_reset.sh

**Files:**
- Create: `scripts/jenkins_reset.sh`

**Purpose:** One-command teardown + clean rebuild of the Jenkins container. Useful after Dockerfile changes.

- [ ] **Step 1: Write the script**

```bash
#!/usr/bin/env bash
set -euo pipefail

echo "==> Stopping Jenkins container..."
docker compose -f docker-compose.jenkins.yml down --remove-orphans

echo "==> Removing old Jenkins image (if any)..."
docker image rm -f "$(docker compose -f docker-compose.jenkins.yml images -q jenkins 2>/dev/null)" 2>/dev/null || true

echo "==> Building new Jenkins image..."
docker compose -f docker-compose.jenkins.yml build --no-cache jenkins

echo "==> Starting Jenkins..."
docker compose -f docker-compose.jenkins.yml up -d

echo ""
echo "Jenkins starting at http://localhost:8085"
echo "Initial admin password (wait ~30s then run):"
echo "  docker exec jenkins cat /var/jenkins_home/secrets/initialAdminPassword"
```

- [ ] **Step 2: Make it executable and verify**

```bash
chmod +x scripts/jenkins_reset.sh
head -5 scripts/jenkins_reset.sh
```

Expected first line: `#!/usr/bin/env bash`

- [ ] **Step 3: Commit**

```bash
git add scripts/jenkins_reset.sh
git commit -m "feat(jenkins): add jenkins_reset.sh for clean rebuild"
```

---

### Task 5: Smoke-test the full pipeline

**No code changes — verification only.**

- [ ] **Step 1: Run the reset script**

```bash
bash scripts/jenkins_reset.sh
```

Expected: container starts, URL printed.

- [ ] **Step 2: Wait for Jenkins to start, then check logs**

```bash
docker logs jenkins --tail 30
```

Expected: no `docker: command not found`, no `make: command not found`, no `docker compose: unknown subcommand`.

- [ ] **Step 3: Verify docker-compose-plugin is present inside the container**

```bash
docker exec jenkins docker compose version
```

Expected output: `Docker Compose version v2.x.x`

- [ ] **Step 4: Verify the workspace path is accessible**

```bash
docker exec jenkins ls /mnt/d/DevOps/EstudoHub_4.0/Jenkinsfile
```

Expected: prints `Jenkinsfile` (not "No such file").

- [ ] **Step 5: Trigger a build via Jenkins UI**

Open `http://localhost:8085`, navigate to your pipeline job, click **Build Now**, watch Console Output.

Confirm all stages complete: Prepare ✓, Tests & Coverage ✓, SonarQube Analysis ✓, Security Check ✓.

---

## Self-Review

**Spec coverage:**
| Requirement | Covered by |
|---|---|
| Map project to `/mnt/d/DevOps/EstudoHub_4.0` in container | Task 2 (already present, confirmed) |
| `working_dir` set | Task 2 (already present, confirmed) |
| `user: root` | Task 2 (already present, confirmed) |
| Docker socket mounted | Task 2 (already present, confirmed) |
| `make`, `curl`, `docker-cli`, `docker-compose-plugin` in image | Task 1 |
| `agent { node { customWorkspace '...' } }` | Task 3 |
| `docker compose run --rm backend pytest tests` | Task 3 |
| SonarQube with correct network mapping | Task 3 (uses `make sonar-scan` which is self-contained; Vault uses `host.docker.internal`) |
| `scripts/jenkins_reset.sh` | Task 4 |

**Placeholder scan:** None found. All steps contain actual commands and complete file content.

**Type consistency:** No shared types across tasks; each task is self-contained shell/YAML/Groovy.
