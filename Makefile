.PHONY: test backend-test frontend-test serve frontend

SHELL := /bin/bash

COMPOSE := docker compose
TEST_DEPS := postgres redis
SERVE_DEPS := postgres redis minio minio-init

# Copy env defaults once so alembic/uvicorn can load local settings.
.env:
	cp .env.example .env

backend-test:
	$(COMPOSE) up -d --wait $(TEST_DEPS)
	cd backend && uv sync && uv run pytest

frontend-test:
	cd frontend && npm install && npm test

test: backend-test frontend-test

# Infra + migrations + worker, then the API in the foreground.
serve: .env
	$(COMPOSE) up -d --wait $(SERVE_DEPS)
	cd backend && uv sync && uv run alembic upgrade head
	cd backend && \
		uv run dramatiq app.queue.actors --processes 1 --threads 2 & \
		trap 'kill $$(jobs -p) 2>/dev/null' EXIT INT TERM; \
		uv run uvicorn app.main:app --reload --host 0.0.0.0 --port 8000

frontend:
	cd frontend && npm install && npm run dev
