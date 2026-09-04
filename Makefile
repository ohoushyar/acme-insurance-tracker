.PHONY: test backend-test frontend-test serve frontend load-fake-data \
	deploy-local destroy-local deploy destroy-aws \
	destroy-staging destroy-production

SHELL := /bin/bash

COMPOSE := docker compose
TEST_DEPS := postgres redis
SERVE_DEPS := postgres redis minio mailpit
NPM_INSTALL := npm install --no-audit --no-fund

TF_LOCAL := infra/terraform/local
IMAGE_TAG ?= $(shell git rev-parse --short HEAD)
API_IMAGE := insurance-tracker-api
FRONTEND_IMAGE := insurance-tracker-frontend
KUBE_CONTEXT ?=
AWS_REGION ?= us-east-1
CONFIRM ?=
DESTROY_CLUSTER ?=
OPENROUTER_API_KEY ?=
ENV ?=

ifneq (,$(wildcard .env))
include .env
export
endif

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

deploy-local: .env
	KUBE_CONTEXT=$(KUBE_CONTEXT) OPENROUTER_API_KEY=$(OPENROUTER_API_KEY) \
		API_IMAGE=$(API_IMAGE) FRONTEND_IMAGE=$(FRONTEND_IMAGE) \
		bash infra/scripts/deploy-local.sh

destroy-local:
	KUBE_CONTEXT=$(KUBE_CONTEXT) OPENROUTER_API_KEY=$(OPENROUTER_API_KEY) \
		bash infra/scripts/destroy-local.sh

deploy:
	@if [ -z "$(ENV)" ]; then echo "ENV=staging or ENV=production is required"; exit 1; fi
	ENV=$(ENV) IMAGE_TAG=$(IMAGE_TAG) AWS_REGION=$(AWS_REGION) \
		OPENROUTER_API_KEY=$(OPENROUTER_API_KEY) \
		bash infra/scripts/deploy-aws.sh

destroy-aws:
	@if [ -z "$(ENV)" ]; then echo "ENV=staging or ENV=production is required"; exit 1; fi
	ENV=$(ENV) IMAGE_TAG=$(IMAGE_TAG) CONFIRM=$(CONFIRM) \
		DESTROY_CLUSTER=$(DESTROY_CLUSTER) \
		OPENROUTER_API_KEY=$(OPENROUTER_API_KEY) \
		bash infra/scripts/destroy-aws.sh

destroy-staging:
	$(MAKE) destroy-aws ENV=staging

destroy-production:
	$(MAKE) destroy-aws ENV=production CONFIRM=$(CONFIRM) DESTROY_CLUSTER=$(DESTROY_CLUSTER)
