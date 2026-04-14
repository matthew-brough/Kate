#!/usr/bin/env bash
# Bootstrap the Kate platform cluster.
# Run once after opening the devcontainer.
set -euo pipefail

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
CLUSTER_NAME="kate"

log() { echo "==> $*"; }

# ── Cluster ──────────────────────────────────────────────────────────────────
log "Creating k3d cluster '${CLUSTER_NAME}'..."
if k3d cluster list | grep -q "^${CLUSTER_NAME}"; then
  log "Cluster already exists — skipping create."
else
  k3d cluster create --config "${SCRIPT_DIR}/k3d-config.yaml"
fi

log "Merging kubeconfig..."
k3d kubeconfig merge "${CLUSTER_NAME}" --kubeconfig-merge-default --kubeconfig-switch-context

log "Waiting for nodes..."
kubectl wait node --all --for=condition=Ready --timeout=120s

# ── Namespaces ───────────────────────────────────────────────────────────────
log "Creating namespaces..."
kubectl create namespace platform   --dry-run=client -o yaml | kubectl apply -f -
kubectl create namespace monitoring --dry-run=client -o yaml | kubectl apply -f -
kubectl create namespace argocd     --dry-run=client -o yaml | kubectl apply -f -

# ── Traefik (ingress) ────────────────────────────────────────────────────────
log "Installing Traefik..."
helm repo add traefik https://traefik.github.io/charts --force-update
helm upgrade --install traefik traefik/traefik \
  --namespace kube-system \
  --set ingressClass.enabled=true \
  --set ingressClass.isDefaultClass=true \
  --wait

log ""
log "Cluster ready. Next: run 'make dev' to start Tilt."
kubectl get nodes -o wide
