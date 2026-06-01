#!/usr/bin/env bash
# Bootstrap the Kate platform cluster.
# Run once after opening the devcontainer.
set -euo pipefail

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
CLUSTER_NAME="kate"
REGISTRY_NAME="registry.localhost"
REGISTRY_HOST="0.0.0.0"
REGISTRY_HOST_PORT="5001"
REGISTRY_CONTAINER_PORT="5000"

log() { echo "==> $*"; }

ensure_helm_repo() {
  local repo_name="$1"
  local repo_url="$2"

  if helm repo list -o yaml | grep -q "name: ${repo_name}"; then
    return
  fi

  helm repo add "${repo_name}" "${repo_url}"
}

ensure_registry() {
  if docker inspect "${REGISTRY_NAME}" >/dev/null 2>&1; then
    local compose_project
    local k3d_cluster
    compose_project="$(docker inspect \
      -f '{{ index .Config.Labels "com.docker.compose.project" }}' \
      "${REGISTRY_NAME}")"
    k3d_cluster="$(docker inspect \
      -f '{{ index .Config.Labels "k3d.cluster" }}' \
      "${REGISTRY_NAME}")"

    if [ -n "${k3d_cluster}" ]; then
      log "Recreating registry '${REGISTRY_NAME}' without cluster ownership label."
      docker rm -f "${REGISTRY_NAME}" >/dev/null
    elif [ "${compose_project}" != "${CLUSTER_NAME}" ]; then
      log "Registry '${REGISTRY_NAME}' already exists without Kate Docker Desktop labels."
      log "Recreate the cluster and registry to move it into the Kate group."
      return
    else
      log "Registry '${REGISTRY_NAME}' already exists — skipping create."
      return
    fi
  fi

  log "Creating labeled local registry '${REGISTRY_NAME}'..."
  docker run -d \
    --name "${REGISTRY_NAME}" \
    --label app=k3d \
    --label "k3d.registry.host=${REGISTRY_HOST}" \
    --label "k3d.registry.hostIP=${REGISTRY_HOST}" \
    --label k3d.role=registry \
    --label "k3s.registry.port.external=${REGISTRY_HOST_PORT}" \
    --label "k3s.registry.port.internal=${REGISTRY_CONTAINER_PORT}" \
    --label "com.docker.compose.project=${CLUSTER_NAME}" \
    --label com.docker.compose.oneoff=False \
    --label com.docker.compose.service=registry \
    -p "${REGISTRY_HOST}:${REGISTRY_HOST_PORT}:${REGISTRY_CONTAINER_PORT}" \
    registry:2 >/dev/null
}

remove_tools_container() {
  local tools_container="k3d-${CLUSTER_NAME}-tools"

  if docker inspect "${tools_container}" >/dev/null 2>&1; then
    log "Removing transient k3d tools container '${tools_container}'..."
    docker rm -f "${tools_container}" >/dev/null
  fi
}

cluster_exists() {
  k3d cluster list --no-headers "${CLUSTER_NAME}" >/dev/null 2>&1
}

cluster_has_nodes() {
  local cluster_info
  cluster_info="$(k3d cluster list --no-headers "${CLUSTER_NAME}")"

  [ "$(echo "${cluster_info}" | awk '{ print $2 }')" != "0/0" ]
}

# ── Cluster ──────────────────────────────────────────────────────────────────
ensure_registry

log "Creating k3d cluster '${CLUSTER_NAME}'..."
if cluster_exists; then
  if ! cluster_has_nodes; then
    log "Cluster '${CLUSTER_NAME}' exists in k3d but has no nodes."
    log "Run 'make cluster-down' and then 'make cluster-up' to recreate it."
    exit 1
  fi
  log "Cluster already exists — skipping create."
else
  k3d cluster create --config "${SCRIPT_DIR}/k3d-config.yaml"
fi
remove_tools_container

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
if helm status traefik --namespace kube-system >/dev/null 2>&1; then
  log "Traefik already installed — skipping Helm install."
else
  log "Installing Traefik..."
  ensure_helm_repo traefik https://traefik.github.io/charts
  helm upgrade --install traefik traefik/traefik \
    --namespace kube-system \
    --set ingressClass.enabled=true \
    --set ingressClass.isDefaultClass=true \
    --wait
fi

log ""
log "Cluster ready. Next: run 'make dev' to start Tilt."
kubectl get nodes -o wide
