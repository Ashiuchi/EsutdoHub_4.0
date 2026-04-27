pipeline {
    agent {
        node {
            label 'built-in'
            customWorkspace '/mnt/c/Dev/EstudoHub_4.0'
        }
    }


    environment {
        VAULT_ADDR  = "http://host.docker.internal:8205"
        PROJECT_DIR = "/mnt/c/Dev/EstudoHub_4.0"
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

                    pdf_list=$(mktemp /tmp/pdf_list.XXXXXX)
                    find "$PROJECT_DIR/sample_editais" -name "*.pdf" > "$pdf_list"

                    while IFS= read -r path; do
                        total=$((total + 1))
                        echo "[UPLOAD] $path"
                        http_code=$(curl -s -o /dev/null -w "%{http_code}" \
                            --max-time 30 \
                            -F "file=@$path" \
                            http://backend:8000/api/v1/upload)
                        if [ "$http_code" = "000" ]; then
                            echo "[ERRO] Falha de conexão (backend inacessível)"
                            failed=$((failed + 1))
                        elif [ -n "$http_code" ] && \
                             [ "$http_code" -ge 200 ] && [ "$http_code" -lt 300 ]; then
                            echo "[OK] HTTP $http_code"
                            success=$((success + 1))
                        else
                            echo "[ERRO] HTTP ${http_code:-desconhecido}"
                            failed=$((failed + 1))
                        fi
                    done < "$pdf_list"

                    rm -f "$pdf_list"
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
