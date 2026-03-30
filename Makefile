.PHONY: help setup dev build up stop restart logs test clean shell backend frontend simulator release

# Default
help: ## Show this help
	@grep -E '^[a-zA-Z_-]+:.*?## .*$$' $(MAKEFILE_LIST) | sort | awk 'BEGIN {FS = ":.*?## "}; {printf "\033[36m%-15s\033[0m %s\n", $$1, $$2}'

# Setup & Run
setup: ## Clone, build, and start everything
	docker compose up --build -d
	@echo "✅ EdgeBrain is running at http://localhost:3000"

dev: ## Start in development mode (with hot reload)
	docker compose up --build

build: ## Build all images
	docker compose build

up: ## Start all services
	docker compose up -d

down: ## Stop all services
	docker compose down

restart: ## Restart all services
	docker compose restart

stop: down ## Alias for down

logs: ## Tail all logs
	docker compose logs -f

logs-backend: ## Tail backend logs
	docker compose logs -f backend

logs-simulator: ## Tail simulator logs
	docker compose logs -f simulator

# Testing
test: ## Run backend tests
	docker compose exec backend python -m pytest tests/ -v --tb=short

test-coverage: ## Run tests with coverage
	docker compose exec backend python -m pytest tests/ -v --cov=app --cov-report=term-missing

# Management
shell: ## Open a shell in the backend container
	docker compose exec backend bash

psql: ## Open PostgreSQL shell
	docker compose exec postgres psql -U edgebrain -d edgebrain

redis-cli: ## Open Redis CLI
	docker compose exec redis redis-cli

# Cleanup
clean: ## Stop and remove all volumes
	docker compose down -v
	@echo "🗑️ All data cleared"

# Individual services
backend: ## Run backend only (native)
	cd backend && \
	pip install -r requirements.txt && \
	uvicorn app.main:app --reload --host 0.0.0.0 --port 8000

frontend: ## Run frontend only (native)
	cd frontend && npm install && npm start

simulator: ## Run simulator only (native)
	cd device-simulator && \
	pip install paho-mqtt==2.0.0 && \
	python simulator.py

# Database
db-init: ## Initialize database
	docker compose exec postgres psql -U edgebrain -d edgebrain -f /docker-entrypoint-initdb.d/init.sql

db-reset: ## Reset database (drops all data)
	docker compose exec postgres psql -U edgebrain -d edgebrain -c "DROP SCHEMA public CASCADE; CREATE SCHEMA public;"
	make db-init

# Release
release: ## Create a new release (usage: make release v=1.1.0)
	@test -n "$(v)" || (echo "Usage: make release v=1.1.0" && exit 1)
	@echo "🚀 Creating release $(v)..."
	sed -i "s/__version__ = \".*\"/__version__ = \"$(v)\"/" backend/app/__init__.py
	sed -i "s/APP_VERSION: str = \".*\"/APP_VERSION: str = \"$(v)\"/" backend/app/core/config.py
	sed -i "s/\"version\": \".*\"/\"version\": \"$(v)\"/" frontend/package.json
	git add -A
	git commit -m "release: v$(v)"
	git tag -a "$(v)" -m "Release v$(v)"
	git push origin master --tags
	@echo "✅ Release $(v) created and tagged"
