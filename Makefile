.PHONY: test backend-test frontend-test serve frontend load-fake-data \
	deploy-local destroy-local deploy destroy-aws \
	destroy-staging destroy-production

SHELL := /bin/bash

COMPOSE := docker compose
TEST_DEPS := postgres redis
SERVE_DEPS := postgres redis minio
NPM_INSTALL := npm install --no-audit --no-fund

K3D_CLUSTER := insurance-tracker
TF_LOCAL := infra/terraform/local
IMAGE_TAG ?= $(shell git rev-parse --short HEAD)
API_IMAGE := insurance-tracker-api
FRONTEND_IMAGE := insurance-tracker-frontend
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
	@command -v k3d >/dev/null || { echo "k3d is required (https://k3d.io)"; exit 1; }
	@command -v terraform >/dev/null || { echo "terraform is required"; exit 1; }
	@command -v docker >/dev/null || { echo "docker is required"; exit 1; }
	@if ! k3d cluster list --no-headers 2>/dev/null | awk '{print $$1}' | grep -qx $(K3D_CLUSTER); then \
		k3d cluster create $(K3D_CLUSTER) --agents 0 --wait -p "8080:80@loadbalancer"; \
	fi
	docker build -t $(API_IMAGE):latest ./backend
	docker build -t $(FRONTEND_IMAGE):latest --build-arg API_UPSTREAM=127.0.0.1:8000 ./frontend
	k3d image import $(API_IMAGE):latest $(FRONTEND_IMAGE):latest -c $(K3D_CLUSTER)
	terraform -chdir=$(TF_LOCAL) init -input=false
	terraform -chdir=$(TF_LOCAL) apply -auto-approve \
		-var="openrouter_api_key=$(OPENROUTER_API_KEY)"
	@echo "Local cluster app: http://localhost:8080"

destroy-local:
	@command -v k3d >/dev/null || { echo "k3d is required (https://k3d.io)"; exit 1; }
	@command -v terraform >/dev/null || { echo "terraform is required"; exit 1; }
	@if [ -f $(TF_LOCAL)/terraform.tfstate ] \
		&& k3d cluster list --no-headers 2>/dev/null | awk '{print $$1}' | grep -qx $(K3D_CLUSTER); then \
		terraform -chdir=$(TF_LOCAL) destroy -auto-approve \
			-var="openrouter_api_key=$(OPENROUTER_API_KEY)" || true; \
	fi
	@if k3d cluster list --no-headers 2>/dev/null | awk '{print $$1}' | grep -qx $(K3D_CLUSTER); then \
		k3d cluster delete $(K3D_CLUSTER); \
	fi

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
