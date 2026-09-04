#!/usr/bin/env bash
set -euo pipefail

ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/../.." && pwd)"
cd "$ROOT"

ENV="${ENV:?ENV=staging or ENV=production is required}"
if [[ "$ENV" != "staging" && "$ENV" != "production" ]]; then
  echo "ENV must be staging or production" >&2
  exit 1
fi

CONFIRM="${CONFIRM:-}"
DESTROY_CLUSTER="${DESTROY_CLUSTER:-}"
IMAGE_TAG="${IMAGE_TAG:-$(git rev-parse --short HEAD)}"
OPENROUTER_API_KEY="${OPENROUTER_API_KEY:-}"
TF_PLATFORM="infra/terraform/aws/platform"
TF_APP="infra/terraform/aws/app"

command -v terraform >/dev/null || { echo "terraform is required" >&2; exit 1; }

if [[ "$ENV" == "production" && "$CONFIRM" != "yes" ]]; then
  echo "Refusing to destroy production without CONFIRM=yes" >&2
  exit 1
fi

app_tfvars="$TF_APP/${ENV}.tfvars"
if [[ ! -f "$app_tfvars" ]]; then
  app_tfvars="$TF_APP/${ENV}.tfvars.example"
fi
platform_tfvars="$TF_PLATFORM/terraform.tfvars"
if [[ ! -f "$platform_tfvars" ]]; then
  platform_tfvars="$TF_PLATFORM/terraform.tfvars.example"
fi

terraform -chdir="$TF_APP" init -input=false
terraform -chdir="$TF_APP" workspace select "$ENV" || terraform -chdir="$TF_APP" workspace new "$ENV"

FRONTEND="$(terraform -chdir="$TF_APP" output -raw frontend_bucket 2>/dev/null || true)"
DOCS="$(terraform -chdir="$TF_APP" output -raw docs_bucket 2>/dev/null || true)"
if [[ -n "$FRONTEND" ]]; then aws s3 rm "s3://${FRONTEND}" --recursive || true; fi
if [[ -n "$DOCS" ]]; then aws s3 rm "s3://${DOCS}" --recursive || true; fi

terraform -chdir="$TF_APP" destroy -auto-approve \
  -var-file="$(basename "$app_tfvars")" \
  -var="image_tag=${IMAGE_TAG}" \
  -var="openrouter_api_key=${OPENROUTER_API_KEY}" || true

if [[ "$DESTROY_CLUSTER" != "yes" ]]; then
  exit 0
fi

other="production"
if [[ "$ENV" == "production" ]]; then
  other="staging"
fi
if terraform -chdir="$TF_APP" workspace list 2>/dev/null | grep -q "$other"; then
  terraform -chdir="$TF_APP" workspace select "$other" >/dev/null
  if terraform -chdir="$TF_APP" state list 2>/dev/null | grep -q .; then
    echo "Refusing to destroy shared EKS; ${other} still has resources" >&2
    exit 1
  fi
fi

terraform -chdir="$TF_PLATFORM" init -input=false
terraform -chdir="$TF_PLATFORM" destroy -auto-approve \
  -var-file="$(basename "$platform_tfvars")"
