#!/usr/bin/env bash
set -euo pipefail

ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/../.." && pwd)"
cd "$ROOT"

ENV="${ENV:?ENV=staging or ENV=production is required}"
if [[ "$ENV" != "staging" && "$ENV" != "production" ]]; then
  echo "ENV must be staging or production" >&2
  exit 1
fi

IMAGE_TAG="${IMAGE_TAG:-$(git rev-parse --short HEAD)}"
AWS_REGION="${AWS_REGION:-us-east-1}"
OPENROUTER_API_KEY="${OPENROUTER_API_KEY:-}"
TF_PLATFORM="infra/terraform/aws/platform"
TF_APP="infra/terraform/aws/app"

command -v terraform >/dev/null || { echo "terraform is required" >&2; exit 1; }
command -v aws >/dev/null || { echo "aws CLI is required" >&2; exit 1; }
command -v docker >/dev/null || { echo "docker is required" >&2; exit 1; }

platform_tfvars="$TF_PLATFORM/terraform.tfvars"
if [[ ! -f "$platform_tfvars" ]]; then
  platform_tfvars="$TF_PLATFORM/terraform.tfvars.example"
fi
app_tfvars="$TF_APP/${ENV}.tfvars"
if [[ ! -f "$app_tfvars" ]]; then
  app_tfvars="$TF_APP/${ENV}.tfvars.example"
fi

terraform -chdir="$TF_PLATFORM" init -input=false
terraform -chdir="$TF_PLATFORM" apply -auto-approve \
  -var-file="$(basename "$platform_tfvars")" \
  -target=module.platform
terraform -chdir="$TF_PLATFORM" apply -auto-approve \
  -var-file="$(basename "$platform_tfvars")"

ECR_URL="$(terraform -chdir="$TF_PLATFORM" output -raw ecr_repository_url)"
aws ecr get-login-password --region "$AWS_REGION" \
  | docker login --username AWS --password-stdin "$ECR_URL"
# EKS nodes are t3.medium (linux/amd64). A native docker build on
# Apple Silicon publishes linux/arm64, which kubelet cannot pull.
# Provenance attestations create an OCI index that some containerd
# versions also reject with "no match for platform in manifest".
docker buildx build \
  --platform linux/amd64 \
  --provenance=false \
  --push \
  -t "${ECR_URL}:${IMAGE_TAG}" \
  ./backend

terraform -chdir="$TF_APP" init -input=false
terraform -chdir="$TF_APP" workspace select "$ENV" || terraform -chdir="$TF_APP" workspace new "$ENV"
if ! terraform -chdir="$TF_APP" apply -auto-approve \
  -var-file="$(basename "$app_tfvars")" \
  -var="image_tag=${IMAGE_TAG}" \
  -var="openrouter_api_key=${OPENROUTER_API_KEY}"; then
  terraform -chdir="$TF_APP" apply -auto-approve \
    -var-file="$(basename "$app_tfvars")" \
    -var="image_tag=${IMAGE_TAG}" \
    -var="openrouter_api_key=${OPENROUTER_API_KEY}"
fi
CF_ID="$(terraform -chdir="$TF_APP" output -raw cloudfront_distribution_id || true)"
if [[ -z "$CF_ID" ]]; then
  terraform -chdir="$TF_APP" apply -auto-approve \
    -var-file="$(basename "$app_tfvars")" \
    -var="image_tag=${IMAGE_TAG}" \
    -var="openrouter_api_key=${OPENROUTER_API_KEY}"
fi

(cd frontend && npm ci && npm run build)
aws s3 sync frontend/dist "s3://$(terraform -chdir="$TF_APP" output -raw frontend_bucket)" --delete
aws cloudfront create-invalidation \
  --distribution-id "$(terraform -chdir="$TF_APP" output -raw cloudfront_distribution_id)" \
  --paths "/*"
echo "App: $(terraform -chdir="$TF_APP" output -raw cloudfront_url)"
