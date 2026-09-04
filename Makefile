.PHONY: test backend-test frontend-test serve frontend load-fake-data

SHELL := /bin/bash

COMPOSE := docker compose
TEST_DEPS := postgres redis
SERVE_DEPS := postgres redis minio
NPM_INSTALL := npm install --no-audit --no-fund

# Copy env defaults once so alembic/uvicorn can load local settings.
.env:
	cp .env.example .env

backend-test:
	$(COMPOSE) up -d --wait $(TEST_DEPS)
	cd backend && uv sync && uv run pytest

frontend/node_modules: frontend/package.json frontend/package-lock.json
	cd frontend && $(NPM_INSTALL)
	touch frontend/node_modules

frontend-test: frontend/node_modules
	cd frontend && npm test

test: backend-test frontend-test

# Infra + migrations + worker, then the API in the foreground.
serve: .env
	$(COMPOSE) up -d --wait $(SERVE_DEPS)
	$(COMPOSE) run --rm --no-deps minio-init
	cd backend && uv sync && uv run alembic upgrade head
	cd backend && { \
		uv run dramatiq app.queue.actors --processes 1 --threads 2 & \
		trap 'kill $$(jobs -p) 2>/dev/null' EXIT INT TERM; \
		uv run uvicorn app.main:app --reload --host 0.0.0.0 --port 8000; \
	}

frontend: frontend/node_modules
	cd frontend && npm run dev

# Wipe and reload the five local demo accounts (see README). Idempotent.
load-fake-data: .env
	$(COMPOSE) up -d --wait postgres redis minio
	$(COMPOSE) run --rm --no-deps minio-init
	cd backend && uv sync && uv run alembic upgrade head
	cd backend && uv run python scripts/seed_demo.py
