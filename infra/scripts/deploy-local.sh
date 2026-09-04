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

NAMESPACE="${NAMESPACE:-default}"
tf_vars=(
  -var="openrouter_api_key=${OPENROUTER_API_KEY}"
  -var="kube_context=${KUBE_CONTEXT}"
)

# Cluster leftovers from a previous apply (or lost local state) must be
# imported. Terraform create fails with "already exists" otherwise.
adopt_existing() {
  local address="$1"
  local kind="$2"
  local name="$3"
  if terraform -chdir="$TF_LOCAL" state list 2>/dev/null | grep -Fxq "$address"; then
    return 0
  fi
  if kubectl --context "$KUBE_CONTEXT" -n "$NAMESPACE" get "$kind" "$name" >/dev/null 2>&1; then
    echo "Adopting existing ${kind}/${name} into Terraform state"
    terraform -chdir="$TF_LOCAL" import -input=false "${tf_vars[@]}" \
      "$address" "${NAMESPACE}/${name}"
  fi
}

adopt_existing module.app.kubernetes_config_map_v1.postgres_init configmap postgres-init
adopt_existing module.app.kubernetes_config_map_v1.app configmap insurance-tracker
adopt_existing module.app.kubernetes_secret_v1.app secret insurance-tracker
adopt_existing module.app.kubernetes_deployment_v1.stack deployment insurance-tracker
adopt_existing module.app.kubernetes_service_v1.frontend service insurance-tracker

terraform -chdir="$TF_LOCAL" apply -auto-approve "${tf_vars[@]}"

echo
echo "Local cluster app (context ${KUBE_CONTEXT}):"
echo "  kubectl --context ${KUBE_CONTEXT} port-forward svc/insurance-tracker 8080:80"
echo "  then open http://localhost:8080"
kubectl --context "$KUBE_CONTEXT" get pod,svc -l app=insurance-tracker
