#!/usr/bin/env bash
# Install KEDA into the cluster.
# Run once after `make cluster-up`, before enabling keda.enabled in worker values.
set -euo pipefail

KEDA_VERSION="${KEDA_VERSION:-2.16.0}"

echo "==> Adding kedacore Helm repo"
helm repo add kedacore https://kedacore.github.io/charts
helm repo update

echo "==> Installing KEDA ${KEDA_VERSION}"
helm upgrade --install keda kedacore/keda \
  --namespace keda \
  --create-namespace \
  --version "${KEDA_VERSION}" \
  --set watchNamespace=platform \
  --wait

echo "==> KEDA ready"
kubectl get pods -n keda
