#!/usr/bin/env bash
set -euo pipefail

ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/../.." && pwd)"
cd "$ROOT"

TF_LOCAL="infra/terraform/local"
OPENROUTER_API_KEY="${OPENROUTER_API_KEY:-}"
HTTPS_PROXY="${HTTPS_PROXY:-}"
HTTP_PROXY="${HTTP_PROXY:-}"
NO_PROXY="${NO_PROXY:-127.0.0.1,localhost,::1}"

command -v terraform >/dev/null || { echo "terraform is required" >&2; exit 1; }

KUBE_CONTEXT="${KUBE_CONTEXT:-}"
if [[ -z "$KUBE_CONTEXT" ]] && command -v kubectl >/dev/null; then
  KUBE_CONTEXT="$(kubectl config current-context 2>/dev/null || true)"
fi

tf_vars=(
  -var="openrouter_api_key=${OPENROUTER_API_KEY}"
  -var="https_proxy=${HTTPS_PROXY}"
  -var="http_proxy=${HTTP_PROXY}"
  -var="no_proxy=${NO_PROXY}"
)
if [[ -n "$KUBE_CONTEXT" ]]; then
  tf_vars+=(-var="kube_context=${KUBE_CONTEXT}")
fi

if [[ -f "${TF_LOCAL}/terraform.tfstate" ]]; then
  terraform -chdir="$TF_LOCAL" init -input=false
  terraform -chdir="$TF_LOCAL" destroy -auto-approve "${tf_vars[@]}" || true
fi

# Objects left in the cluster after lost/empty Terraform state are not
# destroyed above. Delete by label so the next deploy-local can create them.
if command -v kubectl >/dev/null && [[ -n "${KUBE_CONTEXT}" ]]; then
  NAMESPACE="${NAMESPACE:-default}"
  kubectl --context "$KUBE_CONTEXT" -n "$NAMESPACE" delete \
    configmap,secret,deployment,service \
    -l app=insurance-tracker \
    --ignore-not-found
fi

echo "Removed the insurance-tracker workload. The local Kubernetes cluster was left running."
