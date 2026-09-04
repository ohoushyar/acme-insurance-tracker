# Insurance Tracker

CRE insurance renewal tracker.

## Intro and Intention

**Why an insurance tracker?**

Data fragmentation turned out to be a genuine, recurring issue in commercial real estate. Owners and operators have to manage several disconnected pieces of their portfolio — mortgage maturities, insurance renewals, compliance deadlines, and more — often with no unified system. A tracking tool could address any one of these individually, or eventually several together.

Looking at what already exists, a handful of companies offer mortgage maturity tracking, but I couldn't find a comparable dedicated solution for insurance renewal tracking. That gap is why I chose to focus here. I recognize that a more rigorous, longer research process would normally inform a decision like this, but given the time constraints, I moved forward based on the research done so far.

**Who's the audience?**

The target user is a property manager or owner overseeing a portfolio — potentially up to a few hundred properties — but the sweet spot is mid-market businesses rather than enterprise. Enterprise-level firms typically already have sophisticated, purpose-built software to manage this. Mid-market firms, by contrast, usually rely on spreadsheets to track these assets, including insurance policies and renewal dates. This application aims to take one recurring, error-prone task off their plate — tracking insurance policies and renewals — that they currently manage manually.

## Architecture

How the pieces fit together:
[docs/architecture.md](docs/architecture.md).

## Build Process

Build-order writeups live in [docs/plans/](docs/plans/). 

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
