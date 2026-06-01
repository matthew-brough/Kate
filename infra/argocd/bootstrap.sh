#!/usr/bin/env bash
set -euo pipefail

ARGOCD_CHART_VERSION="${ARGOCD_CHART_VERSION:-7.7.0}"
SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
REPO_ROOT="$(cd "${SCRIPT_DIR}/../.." && pwd)"

ensure_helm_repo() {
  local repo_name="$1"
  local repo_url="$2"

  if helm repo list -o yaml | grep -q "name: ${repo_name}"; then
    return
  fi

  helm repo add "${repo_name}" "${repo_url}"
}

if helm status argocd --namespace argocd >/dev/null 2>&1; then
  echo "==> ArgoCD already installed — skipping Helm install."
else
  echo "==> Ensuring argo Helm repo"
  ensure_helm_repo argo https://argoproj.github.io/argo-helm

  echo "==> Installing ArgoCD ${ARGOCD_CHART_VERSION} in namespace argocd"
  echo "==> Dev-only: configuring argocd-server with configs.params.server.insecure=true"
  helm upgrade --install argocd argo/argo-cd \
    --namespace argocd --create-namespace \
    --version "${ARGOCD_CHART_VERSION}" \
    --set "configs.params.server\.insecure=true" \
    --wait
fi

echo "==> Applying root Applications"
kubectl apply -f "${REPO_ROOT}/gitops/root-dev.yaml"
kubectl apply -f "${REPO_ROOT}/gitops/root-staging.yaml"

echo ""
echo "ArgoCD UI: kubectl port-forward svc/argocd-server -n argocd 8080:80"
echo "Initial admin password: kubectl -n argocd get secret argocd-initial-admin-secret -o jsonpath='{.data.password}' | base64 -d"
