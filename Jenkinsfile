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
