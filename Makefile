.PHONY: up down logs ps restart sonar test-backend

COMPOSE := docker compose

up:
	$(COMPOSE) up -d

down:
	$(COMPOSE) down

logs:
	$(COMPOSE) logs -f

ps:
	$(COMPOSE) ps

restart:
	$(COMPOSE) restart

sonar:
	./run-sonar.sh

test-backend:
	mkdir -p backend/test-reports && (python3 -m pytest backend/tests --cov=backend/app --cov-report=xml:backend/test-reports/coverage.xml --cov-report=term-missing || pytest backend/tests --cov=backend/app --cov-report=xml:backend/test-reports/coverage.xml --cov-report=term-missing)
