# Insurance Tracker

CRE insurance renewal tracker. How the pieces fit together:
[docs/architecture.md](docs/architecture.md). Build-order writeups live
in [docs/plans/](docs/plans/). Cluster deploy is documented in
[docs/plans/10-deployment.md](docs/plans/10-deployment.md).

## Demo accounts (local only)

Presenter script (start servers, seed, logins, stop):
[docs/demo.md](docs/demo.md).

## Prerequisites

- [uv](https://docs.astral.sh/uv/)
- Node.js 22+
- Docker (for Postgres, Redis, MinIO, and optional full-stack Compose)
- An [OpenRouter](https://openrouter.ai/) API key for live extraction (not
  required for tests; CI uses a fake LLM)

For **cluster** deploy (optional): a local Kubernetes (Rancher Desktop
is enough), `kubectl`, [Terraform](https://www.terraform.io/) 1.5+, and
the AWS CLI (production).

## Local development

[docs/development.md](docs/development.md)

## Deployment

[docs/deployment.md](docs/deployment.md)
