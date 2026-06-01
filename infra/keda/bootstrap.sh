#!/usr/bin/env bash
# Install KEDA into the cluster.
# Run once after `make cluster-up`, before enabling keda.enabled in worker values.
set -euo pipefail

KEDA_VERSION="${KEDA_VERSION:-2.16.0}"

ensure_helm_repo() {
  local repo_name="$1"
  local repo_url="$2"

  if helm repo list -o yaml | grep -q "name: ${repo_name}"; then
    return
  fi

  helm repo add "${repo_name}" "${repo_url}"
}

wait_for_keda() {
  kubectl -n keda rollout status deploy/keda-operator --timeout=180s
  kubectl -n keda rollout status deploy/keda-operator-metrics-apiserver --timeout=180s
  kubectl -n keda rollout status deploy/keda-admission-webhooks --timeout=180s
}

if helm status keda --namespace keda >/dev/null 2>&1; then
  if wait_for_keda; then
    echo "==> KEDA already installed — skipping Helm install."
    kubectl get pods -n keda
    exit 0
  fi
  echo "==> Existing KEDA release is not ready — reconciling Helm release."
fi

echo "==> Ensuring kedacore Helm repo"
ensure_helm_repo kedacore https://kedacore.github.io/charts

echo "==> Installing KEDA ${KEDA_VERSION}"
helm upgrade --install keda kedacore/keda \
  --namespace keda \
  --create-namespace \
  --version "${KEDA_VERSION}" \
  --wait

echo "==> KEDA ready"
wait_for_keda
kubectl get pods -n keda
