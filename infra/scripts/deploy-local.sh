#!/usr/bin/env bash
set -euo pipefail

ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/../.." && pwd)"
cd "$ROOT"

TF_LOCAL="infra/terraform/local"
API_IMAGE="${API_IMAGE:-insurance-tracker-api}"
FRONTEND_IMAGE="${FRONTEND_IMAGE:-insurance-tracker-frontend}"
OPENROUTER_API_KEY="${OPENROUTER_API_KEY:-}"

command -v kubectl >/dev/null || { echo "kubectl is required" >&2; exit 1; }
command -v terraform >/dev/null || { echo "terraform is required" >&2; exit 1; }
command -v docker >/dev/null || { echo "docker is required" >&2; exit 1; }

KUBE_CONTEXT="${KUBE_CONTEXT:-$(kubectl config current-context)}"
if [[ -z "$KUBE_CONTEXT" ]]; then
  echo "No kubecontext. Start Rancher Desktop (or another local cluster) and retry." >&2
  exit 1
fi

if ! kubectl --context "$KUBE_CONTEXT" cluster-info >/dev/null 2>&1; then
  echo "Cannot reach Kubernetes context '${KUBE_CONTEXT}'." >&2
  echo "Start Rancher Desktop (or point kubectl at a local cluster) and retry." >&2
  exit 1
fi

echo "Using kubecontext ${KUBE_CONTEXT}"

docker build -t "${API_IMAGE}:latest" ./backend
docker build -t "${FRONTEND_IMAGE}:latest" --build-arg API_UPSTREAM=127.0.0.1:8000 ./frontend
KUBE_CONTEXT="$KUBE_CONTEXT" bash infra/scripts/load-local-images.sh \
  "${API_IMAGE}:latest" "${FRONTEND_IMAGE}:latest"

terraform -chdir="$TF_LOCAL" init -input=false
terraform -chdir="$TF_LOCAL" apply -auto-approve \
  -var="openrouter_api_key=${OPENROUTER_API_KEY}" \
  -var="kube_context=${KUBE_CONTEXT}"

echo
echo "Local cluster app (context ${KUBE_CONTEXT}):"
echo "  kubectl --context ${KUBE_CONTEXT} port-forward svc/insurance-tracker 8080:80"
echo "  then open http://localhost:8080"
kubectl --context "$KUBE_CONTEXT" get pod,svc -l app=insurance-tracker
