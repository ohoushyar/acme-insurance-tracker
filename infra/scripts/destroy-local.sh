#!/usr/bin/env bash
set -euo pipefail

ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/../.." && pwd)"
cd "$ROOT"

TF_LOCAL="infra/terraform/local"
OPENROUTER_API_KEY="${OPENROUTER_API_KEY:-}"

command -v terraform >/dev/null || { echo "terraform is required" >&2; exit 1; }

KUBE_CONTEXT="${KUBE_CONTEXT:-}"
if [[ -z "$KUBE_CONTEXT" ]] && command -v kubectl >/dev/null; then
  KUBE_CONTEXT="$(kubectl config current-context 2>/dev/null || true)"
fi

tf_vars=(-var="openrouter_api_key=${OPENROUTER_API_KEY}")
if [[ -n "$KUBE_CONTEXT" ]]; then
  tf_vars+=(-var="kube_context=${KUBE_CONTEXT}")
fi

if [[ -f "${TF_LOCAL}/terraform.tfstate" ]]; then
  terraform -chdir="$TF_LOCAL" init -input=false
  terraform -chdir="$TF_LOCAL" destroy -auto-approve "${tf_vars[@]}" || true
fi

echo "Removed the insurance-tracker workload. The local Kubernetes cluster was left running."
