#!/usr/bin/env bash
set -euo pipefail

PROM_CHART_VERSION="${PROM_CHART_VERSION:-67.9.0}"
LOKI_CHART_VERSION="${LOKI_CHART_VERSION:-6.6.4}"
PROMTAIL_CHART_VERSION="${PROMTAIL_CHART_VERSION:-6.16.5}"
TEMPO_CHART_VERSION="${TEMPO_CHART_VERSION:-1.10.3}"
OTEL_CHART_VERSION="${OTEL_CHART_VERSION:-0.111.0}"

REPO_ROOT="$(git -C "$(dirname "$0")" rev-parse --show-toplevel)"
VALUES="${REPO_ROOT}/infra/observability/values"

helm repo add prometheus-community https://prometheus-community.github.io/helm-charts
helm repo add grafana https://grafana.github.io/helm-charts
helm repo add open-telemetry https://open-telemetry.github.io/opentelemetry-helm-charts
helm repo update

helm upgrade --install kube-prometheus-stack prometheus-community/kube-prometheus-stack \
  --namespace observability --create-namespace \
  --version "${PROM_CHART_VERSION}" \
  -f "${VALUES}/prometheus-stack.yaml" \
  --wait --timeout 15m

helm upgrade --install loki grafana/loki \
  --namespace observability \
  --version "${LOKI_CHART_VERSION}" \
  -f "${VALUES}/loki.yaml" \
  --wait

helm upgrade --install promtail grafana/promtail \
  --namespace observability \
  --version "${PROMTAIL_CHART_VERSION}" \
  -f "${VALUES}/promtail.yaml" \
  --wait

helm upgrade --install tempo grafana/tempo \
  --namespace observability \
  --version "${TEMPO_CHART_VERSION}" \
  -f "${VALUES}/tempo.yaml" \
  --wait

helm upgrade --install otel-collector open-telemetry/opentelemetry-collector \
  --namespace observability \
  --version "${OTEL_CHART_VERSION}" \
  -f "${VALUES}/otel-collector.yaml" \
  --wait

kubectl apply -f "${REPO_ROOT}/infra/observability/dashboards/"

echo ""
echo "Observability stack installed in namespace: observability"
echo ""
echo "Access:"
echo "  Grafana:    kubectl -n observability port-forward svc/kube-prometheus-stack-grafana 3000:80"
echo "              http://localhost:3000  (admin / admin)"
echo "  Prometheus: kubectl -n observability port-forward svc/kube-prometheus-stack-prometheus 9090:9090"
echo "              http://localhost:9090"
