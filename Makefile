.PHONY: help cluster-up cluster-down cold-start dev test lint lock build

REGISTRY    := registry.localhost:5001
CLUSTER     := kate
SERVICES    := $(wildcard services/*/.)
SERVICE_NAMES := $(patsubst services/%/.,%,$(SERVICES))

# Exclude the _template pseudo-service from build/test targets
REAL_SERVICES := $(filter-out _template,$(SERVICE_NAMES))

help: ## Show this help
	@grep -E '^[a-zA-Z_-]+:.*?## .*$$' $(MAKEFILE_LIST) \
	  | awk 'BEGIN {FS = ":.*?## "}; {printf "\033[36m%-20s\033[0m %s\n", $$1, $$2}'

# ── Cluster ──────────────────────────────────────────────────────────────────

cluster-up: ## Create k3d cluster and bootstrap ingress + namespaces
	@bash infra/bootstrap.sh

cluster-down: ## Destroy the k3d cluster (destructive)
	@docker rm -f registry.localhost k3d-$(CLUSTER)-tools >/dev/null 2>&1 || true
	@k3d cluster delete $(CLUSTER) || true
	@docker network rm k3d-$(CLUSTER) >/dev/null 2>&1 || true

keda-up: ## Install KEDA (queue-depth HPA for worker; run once after cluster-up)
	@bash infra/keda/bootstrap.sh

argocd-up: ## Install ArgoCD and apply root app-of-apps (run once after cluster-up)
	@bash infra/argocd/bootstrap.sh

obs-up: ## Install kube-prometheus-stack, Loki, Promtail, Tempo, OTel Collector
	@bash -c 'set -a; [ ! -f .env ] || . ./.env; set +a; bash infra/observability/bootstrap.sh'

cold-start: cluster-up keda-up obs-up ## Full cold-start: cluster + KEDA + observability, then `tilt up`
	tilt up

# ── Dev loop ─────────────────────────────────────────────────────────────────

dev: ## Start Tilt (rebuild + live-sync on save)
	tilt up

dev-stop: ## Stop Tilt
	tilt down

# ── Python deps ──────────────────────────────────────────────────────────────

lock: ## Generate uv.lock for every service (run inside devcontainer)
	@for svc in $(REAL_SERVICES); do \
	  echo "==> Locking $$svc"; \
	  (cd services/$$svc && uv lock); \
	done

# ── Quality ──────────────────────────────────────────────────────────────────

test: ## Run pytest for every service
	@for svc in $(REAL_SERVICES); do \
	  echo "==> Testing $$svc"; \
	  (cd services/$$svc && uv run pytest); \
	done

lint: ## ruff check + pyright for every service
	@for svc in $(REAL_SERVICES); do \
	  echo "==> Linting $$svc"; \
	  (cd services/$$svc && \
	    uv run ruff check src/ $$([ -d tests ] && echo tests/) && \
	    uv run pyright src/); \
	done

fmt: ## ruff format every service
	@for svc in $(REAL_SERVICES); do \
	  (cd services/$$svc && uv run ruff format src/ tests/); \
	done

# ── Images ───────────────────────────────────────────────────────────────────

build: ## Build all service images (prod target)
	@for svc in $(REAL_SERVICES); do \
	  echo "==> Building $$svc"; \
	  docker build --target production -t $(REGISTRY)/$$svc:dev services/$$svc; \
	done

push: build ## Push all images to local registry
	@for svc in $(REAL_SERVICES); do \
	  docker push $(REGISTRY)/$$svc:dev; \
	done

# ── Helm ─────────────────────────────────────────────────────────────────────

helm-lint: ## helm lint all charts
	@for chart in charts/*/.; do \
	  name=$$(basename $$chart); \
	  [ "$$name" = "_template" ] && continue; \
	  echo "==> Linting chart $$name"; \
	  helm lint $$chart; \
	done

dashboards: ## Compile Jsonnet dashboards and apply as Grafana ConfigMaps (requires jsonnet)
	@for f in dashboards/*.jsonnet; do \
	  name=$$(basename $$f .jsonnet); \
	  jsonnet -J dashboards $$f > /tmp/$$name.json; \
	  kubectl create configmap $$name \
	    --from-file=$$name.json=/tmp/$$name.json \
	    --namespace observability \
	    --dry-run=client -o yaml \
	  | kubectl label --local -f - grafana_dashboard=1 -o yaml \
	  | kubectl apply -f -; \
	done

.DEFAULT_GOAL := help
