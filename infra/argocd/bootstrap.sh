#!/usr/bin/env bash
set -euo pipefail

ARGOCD_CHART_VERSION="${ARGOCD_CHART_VERSION:-7.7.0}"
REPO_ROOT="$(git -C "$(dirname "$0")" rev-parse --show-toplevel)"

echo "==> Adding argo helm repo"
helm repo add argo https://argoproj.github.io/argo-helm
helm repo update

echo "==> Installing ArgoCD ${ARGOCD_CHART_VERSION} in namespace argocd"
helm upgrade --install argocd argo/argo-cd \
  --namespace argocd --create-namespace \
  --version "${ARGOCD_CHART_VERSION}" \
  --set "configs.params.server\.insecure=true" \
  --wait

echo "==> Applying root Applications"
kubectl apply -f "${REPO_ROOT}/gitops/root-dev.yaml"
kubectl apply -f "${REPO_ROOT}/gitops/root-staging.yaml"

echo ""
echo "ArgoCD UI: kubectl port-forward svc/argocd-server -n argocd 8080:80"
ARGOCD_PASS=$(kubectl -n argocd get secret argocd-initial-admin-secret \
  -o jsonpath="{.data.password}" | base64 -d)
echo "Initial admin password: ${ARGOCD_PASS}"
