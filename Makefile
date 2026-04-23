.PHONY: sonar-up sonar-down sonar-init sonar-scan test-backend

sonar-up:
	docker compose -f docker-compose.sonar.yml up -d

sonar-down:
	docker compose -f docker-compose.sonar.yml down

sonar-init:
	bash scripts/setup_sonar.sh

sonar-scan:
	docker compose -f docker-compose.sonar.yml up -d --wait sonarqube
	docker compose -f docker-compose.sonar.yml run --rm sonar-scanner

test-backend:
	mkdir -p backend/test-reports && (python3 -m pytest backend/tests --cov=backend/app --cov-report=xml:backend/test-reports/coverage.xml --cov-report=term-missing || pytest backend/tests --cov=backend/app --cov-report=xml:backend/test-reports/coverage.xml --cov-report=term-missing)

vault-up:
	docker compose -f docker-compose.vault.yml up -d

vault-down:
	docker compose -f docker-compose.vault.yml down

vault-clean:
	docker compose -f docker-compose.vault.yml down -v
	rm -f .vault_keys.txt

vault-init:
	chmod +x scripts/setup_vault.sh
	bash scripts/setup_vault.sh

jenkins-up:
	docker compose -f docker-compose.jenkins.yml up -d

jenkins-down:
	docker compose -f docker-compose.jenkins.yml down

jenkins-logs:
	docker logs -f jenkins

jenkins-password:
	@docker exec jenkins cat /var/jenkins_home/secrets/initialAdminPassword
