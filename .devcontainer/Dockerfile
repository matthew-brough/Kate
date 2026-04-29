FROM mcr.microsoft.com/devcontainers/base:ubuntu-24.04

SHELL ["/bin/bash", "-euo", "pipefail", "-c"]

# ── System packages ──────────────────────────────────────────────────────────
RUN apt-get update && apt-get install -y --no-install-recommends \
        ca-certificates \
        curl \
        git \
        gnupg \
        jq \
        lsb-release \
        make \
        unzip \
    && rm -rf /var/lib/apt/lists/*

# ── uv (Python version manager + package manager) ────────────────────────────
RUN curl -LsSf https://astral.sh/uv/install.sh | env UV_INSTALL_DIR=/usr/local/bin sh

# ── Python 3.14 ──────────────────────────────────────────────────────────────
RUN uv python install 3.14

# ── kubectl ──────────────────────────────────────────────────────────────────
RUN curl -fsSL "https://dl.k8s.io/release/$(curl -fsSL https://dl.k8s.io/release/stable.txt)/bin/linux/amd64/kubectl" \
        -o /usr/local/bin/kubectl \
    && chmod +x /usr/local/bin/kubectl

# ── k3d ──────────────────────────────────────────────────────────────────────
RUN curl -fsSL https://raw.githubusercontent.com/k3d-io/k3d/main/install.sh | bash

# ── Helm ─────────────────────────────────────────────────────────────────────
RUN curl -fsSL https://raw.githubusercontent.com/helm/helm/main/scripts/get-helm-3 | bash

# ── ArgoCD CLI ───────────────────────────────────────────────────────────────
RUN curl -fsSL -o /usr/local/bin/argocd \
        "https://github.com/argoproj/argo-cd/releases/latest/download/argocd-linux-amd64" \
    && chmod +x /usr/local/bin/argocd

# ── Tilt ─────────────────────────────────────────────────────────────────────
RUN curl -fsSL https://raw.githubusercontent.com/tilt-dev/tilt/master/scripts/install.sh | bash

# ── chart-testing (ct) ───────────────────────────────────────────────────────
RUN CT_VER=$(curl -fsSL https://api.github.com/repos/helm/chart-testing/releases/latest \
        | jq -r '.tag_name' | tr -d 'v') \
    && curl -fsSL "https://github.com/helm/chart-testing/releases/download/v${CT_VER}/chart-testing_${CT_VER}_linux_amd64.tar.gz" \
        | tar -xz -C /usr/local/bin ct

# ── kubeconform ──────────────────────────────────────────────────────────────
RUN KC_VER=$(curl -fsSL https://api.github.com/repos/yannh/kubeconform/releases/latest \
        | jq -r '.tag_name' | tr -d 'v') \
    && curl -fsSL "https://github.com/yannh/kubeconform/releases/download/v${KC_VER}/kubeconform-linux-amd64.tar.gz" \
        | tar -xz -C /usr/local/bin kubeconform

# ── Ensure vscode user can use Docker socket (added by docker-outside-of-docker feature) ─
RUN usermod -aG docker vscode 2>/dev/null || true
