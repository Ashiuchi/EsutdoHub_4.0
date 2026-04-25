# Jenkinsfile — Mass Ingestion & Extraction Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Add a resilient `Mass Ingestion & Extraction` stage to the Jenkinsfile that uploads all 25 PDFs from `sample_editais/` to `http://backend:8000/upload` and prints a success/failure summary in the Jenkins log.

**Architecture:** A single `sh` block inside the new stage uses `find` + a `while` loop over a temp file to avoid subshell variable scope issues, `curl` with `--max-time 30` per file, HTTP status code inspection for pass/fail classification, and always exits 0 so the stage never fails the pipeline. Jenkins runs on the `estudohub_40_default` Docker network, so `backend` resolves by service name.

**Tech Stack:** Jenkins Declarative Pipeline (Groovy), POSIX shell, curl

---

## File Map

| Action | File | Responsibility |
|--------|------|----------------|
| Modify | `Jenkinsfile` | Add `Mass Ingestion & Extraction` stage after `Security Check` |

---

### Task 1: Add Mass Ingestion & Extraction Stage to Jenkinsfile

**Files:**
- Modify: `Jenkinsfile` (insert new stage between `Security Check` closing brace and `}` of `stages`)

- [ ] **Step 1.1: Verify current Jenkinsfile structure**

Run:
```bash
grep -n "stage\|^    }" Jenkinsfile
```

Expected output (confirm `Security Check` is the last stage before `stages` closes):
```
16:        stage('Prepare') {
25:        stage('Tests & Coverage') {
37:        stage('SonarQube Analysis') {
44:        stage('Security Check') {
51:    }
```

- [ ] **Step 1.2: Write the new Jenkinsfile**

Replace the entire content of `Jenkinsfile` with:

```groovy
pipeline {
    agent {
        node {
            label 'built-in'
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

        stage('Mass Ingestion & Extraction') {
            steps {
                echo 'Iniciando ingestão em massa dos editais de sample_editais/...'
                sh '''
                    set +e
                    success=0
                    failed=0
                    total=0

                    find sample_editais -name "*.pdf" > /tmp/pdf_list.txt

                    while IFS= read -r path; do
                        total=$((total + 1))
                        echo "[UPLOAD] $path"
                        http_code=$(curl -s -o /dev/null -w "%{http_code}" \
                            --max-time 30 \
                            -F "file=@$path" \
                            http://backend:8000/upload)
                        if [ -n "$http_code" ] && \
                           [ "$http_code" -ge 200 ] && [ "$http_code" -lt 300 ]; then
                            echo "[OK] HTTP $http_code"
                            success=$((success + 1))
                        else
                            echo "[ERRO] HTTP ${http_code:-connection_failed}"
                            failed=$((failed + 1))
                        fi
                    done < /tmp/pdf_list.txt

                    rm -f /tmp/pdf_list.txt
                    echo ""
                    echo "=== RESUMO DA INGESTÃO ==="
                    echo "Total:   $total editais"
                    echo "Sucesso: $success"
                    echo "Falhas:  $failed"
                '''
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

- [ ] **Step 1.3: Validate that the new stage is in the right position**

Run:
```bash
grep -n "stage(" Jenkinsfile
```

Expected output:
```
16:        stage('Prepare') {
25:        stage('Tests & Coverage') {
37:        stage('SonarQube Analysis') {
44:        stage('Security Check') {
52:        stage('Mass Ingestion & Extraction') {
```

- [ ] **Step 1.4: Verify sample_editais has PDFs the stage will find**

Run:
```bash
find sample_editais -name "*.pdf" | wc -l
```

Expected output: `25` (or more — any positive number confirms the loop has work to do).

- [ ] **Step 1.5: Smoke-test the curl command against the live backend**

Run (from the project root, not inside a container):
```bash
first_pdf=$(find sample_editais -name "*.pdf" | head -1)
echo "Testing with: $first_pdf"
http_code=$(curl -s -o /dev/null -w "%{http_code}" \
    --max-time 30 \
    -F "file=@$first_pdf" \
    http://localhost:8000/upload)
echo "HTTP response: $http_code"
```

Expected output: `HTTP response: 200` (or `202`). Confirms the endpoint accepts multipart uploads before triggering the full pipeline.

- [ ] **Step 1.6: Commit**

```bash
git add Jenkinsfile
git commit -m "feat(ci): add Mass Ingestion & Extraction stage to Jenkinsfile"
```

---

## Notes

- The stage uses `http://backend:8000/upload` (not `localhost`) because Jenkins runs inside the `estudohub_40_default` Docker network where `backend` is the service hostname.
- `IFS= read -r` preserves spaces in filenames (e.g., `"Edital casa da moeda.pdf"`).
- `"file=@$path"` double-quotes protect the curl argument from shell word-splitting on spaces.
- The stage always exits 0 (`set +e` + no explicit `exit 1`) — failures are logged but never abort the pipeline.
- Processing happens asynchronously on the backend; the pipeline completes after all uploads are submitted, not after processing finishes. Track extraction progress in the Cockpit (frontend).
