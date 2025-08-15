# Career Mirror - MentorME 2.0 Backend
.PHONY: help build up down test test-coverage clean logs shell db-shell lint format

# Default target
help: ## Show this help message
	@echo "Career Mirror - Available Commands:"
	@echo ""
	@grep -E '^[a-zA-Z_-]+:.*?## .*$$' $(MAKEFILE_LIST) | awk 'BEGIN {FS = ":.*?## "}; {printf "  %-15s %s\n", $$1, $$2}'
	@echo ""

# Development Commands
build: ## Build the Docker containers
	docker-compose build

up: ## Start the application with Docker Compose
	docker-compose up -d

down: ## Stop the application
	docker-compose down

restart: ## Restart the application
	docker-compose restart

logs: ## View application logs
	docker-compose logs -f app

db-logs: ## View database logs  
	docker-compose logs -f db

# Development Tools
shell: ## Access application shell
	docker-compose exec app bash

db-shell: ## Access PostgreSQL shell
	docker-compose exec db psql -U postgres -d career_mirror

# Testing
test: ## Run all tests
	docker-compose exec app python -m pytest -v

test-unit: ## Run unit tests only
	docker-compose exec app python -m pytest -v -m "not integration"

test-integration: ## Run integration tests only
	docker-compose exec app python -m pytest -v -m integration

test-module: ## Run tests for specific module (Usage: make test-module MODULE=jobs)
	docker-compose exec app python -m pytest "app/$(MODULE)/tests" -v

test-coverage: ## Run tests with coverage report
	docker-compose exec app python -m pytest \
		--cov=app \
		--cov-report=term-missing \
		--cov-report=html \
		--cov-fail-under=85

test-watch: ## Run tests in watch mode
	docker-compose exec app python -m pytest -f

# Code Quality
lint: ## Run linting
	docker-compose exec app python -m flake8 app/ --max-line-length=88 --extend-ignore=E203,W503

format: ## Format code with black
	docker-compose exec app python -m black app/ --line-length=88

# Database Operations  
db-migrate: ## Run database migrations
	docker-compose exec app python -c "from app.db import init_db; import asyncio; asyncio.run(init_db())"

db-reset: ## Reset database (WARNING: This will delete all data)
	docker-compose down -v
	docker-compose up -d db
	sleep 5
	docker-compose up -d app

# API Testing
api-test: ## Test API endpoints manually
	@echo "Testing API endpoints..."
	@echo "Health check:"
	curl -s http://localhost:8000/healthz | jq '.'
	@echo "\nAPI Documentation available at: http://localhost:8000/docs"

# Sample Data
load-samples: ## Load sample CV and job data
	@echo "Loading sample profile..."
	curl -X POST "http://localhost:8000/profiles/" \
	  -H "Content-Type: application/json" \
	  -d @samples/cv_sample.json | jq '.'
	@echo "\nLoading sample job..."
	curl -X POST "http://localhost:8000/jobs/" \
	  -H "Content-Type: application/json" \
	  -d @samples/job_sample.json | jq '.'

create-match: ## Create a sample match (requires profile_id and job_id)
	curl -X POST "http://localhost:8000/matches/" \
	  -H "Content-Type: application/json" \
	  -d '{"profile_id": 1, "job_id": 1}' | jq '.'

# Cleanup
clean: ## Clean up containers and volumes
	docker-compose down -v
	docker system prune -f

clean-all: ## Clean everything including images
	docker-compose down -v
	docker system prune -a -f

# Development Setup
dev-setup: ## Complete development setup
	@echo "Setting up Career Mirror development environment..."
	make build
	make up
	@echo "Waiting for services to start..."
	sleep 10
	make db-migrate
	@echo ""
	@echo "✅ Setup complete! Services available at:"
	@echo "   API: http://localhost:8000"
	@echo "   Docs: http://localhost:8000/docs"
	@echo "   Health: http://localhost:8000/healthz"
	@echo ""
	@echo "Run 'make test' to verify installation"

# Performance Testing
load-test: ## Run simple load test (requires wrk)
	@command -v wrk >/dev/null 2>&1 || { echo "wrk is required for load testing. Install with: brew install wrk"; exit 1; }
	wrk -t4 -c100 -d30s --latency http://localhost:8000/healthz

# Monitoring
monitor: ## Show container stats
	docker-compose ps
	@echo ""
	docker stats --no-stream

# Quick Commands for Interview Demo
demo: ## Quick demo setup with sample data
	make dev-setup
	sleep 5
	@echo "Loading demo data..."
	make load-samples
	sleep 2
	make create-match
	@echo ""
	@echo "🎉 Demo ready! Check out:"
	@echo "   API Docs: http://localhost:8000/docs"
	@echo "   Profile Report: http://localhost:8000/reports/1"

# Backup and Restore
backup: ## Backup database
	docker-compose exec db pg_dump -U postgres career_mirror > backup_$(shell date +%Y%m%d_%H%M%S).sql

restore: ## Restore database (set BACKUP_FILE variable)
	@test -n "$(BACKUP_FILE)" || { echo "Usage: make restore BACKUP_FILE=backup_file.sql"; exit 1; }
	docker-compose exec -T db psql -U postgres career_mirror < $(BACKUP_FILE)
