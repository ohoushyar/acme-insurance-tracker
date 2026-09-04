#!/usr/bin/env bash
# Load locally built images into the cluster runtime.
# Rancher Desktop / k3s uses containerd (nerdctl -n k8s.io).
# Docker Desktop and Rancher Desktop+dockerd share the docker image store.
# k3d needs `k3d image import`.
set -euo pipefail

if [[ $# -lt 1 ]]; then
  echo "usage: $0 <image> [image...]" >&2
  exit 1
fi

KUBE_CONTEXT="${KUBE_CONTEXT:-$(kubectl config current-context)}"
runtime="$(kubectl --context "$KUBE_CONTEXT" get nodes \
  -o jsonpath='{.items[0].status.nodeInfo.containerRuntimeVersion}' 2>/dev/null || true)"

nerdctl_bin=""
for candidate in nerdctl "${HOME}/.rd/bin/nerdctl" /usr/local/bin/nerdctl; do
  if command -v "$candidate" >/dev/null 2>&1 || [[ -x "$candidate" ]]; then
    nerdctl_bin="$candidate"
    break
  fi
done

load_one() {
  local image="$1"
  if [[ "$KUBE_CONTEXT" == k3d-* ]]; then
    command -v k3d >/dev/null || {
      echo "k3d is required to import images into context ${KUBE_CONTEXT}" >&2
      exit 1
    }
    k3d image import "$image" -c "${KUBE_CONTEXT#k3d-}"
    return
  fi
  if [[ "$runtime" == containerd://* ]]; then
    if [[ -z "$nerdctl_bin" ]]; then
      echo "Cluster runtime is containerd (${KUBE_CONTEXT}) but nerdctl was not found." >&2
      echo "For Rancher Desktop: install nerdctl (Preferences → Applications → nerdctl)" >&2
      echo "or switch the container engine to dockerd (moby), then retry." >&2
      exit 1
    fi
    docker save "$image" | "$nerdctl_bin" --namespace k8s.io load
    return
  fi
  echo "Using docker image store for ${image} (runtime ${runtime:-unknown}, IfNotPresent)."
}

for image in "$@"; do
  load_one "$image"
done
