FROM mcr.microsoft.com/devcontainers/base:ubuntu-24.04@sha256:d94c97dd9cacf183d0a6fd12a8e87b526e9e928307674ae9c94139139c0c6eae

SHELL ["/bin/bash", "-euo", "pipefail", "-c"]

ARG UV_VERSION=0.11.11
ARG UV_SHA256=a767848254391855c96df271e9ca8b7f72dd172d310460447853d25d907b9ae0
ARG KUBECTL_VERSION=1.36.0
ARG KUBECTL_SHA256=123d8c8844f46b1244c547fffb3c17180c0c26dac9890589fe7e67763298748e
ARG K3D_VERSION=5.8.3
ARG K3D_SHA256=dbaa79a76ace7f4ca230a1ff41dc7d8a5036a8ad0309e9c54f9bf3836dbe853e
ARG HELM_VERSION=3.20.2
ARG HELM_SHA256=258e830a9e613c8a7a302d6059b4bb3b9758f2f3e1bb8ea0d707ce10a9a72fea
ARG ARGOCD_VERSION=3.4.1
ARG ARGOCD_SHA256=0c7bc33afe6ba9d3ff713e482975b5a8bc83efe208fce4eb24d27478beb3cb90
ARG TILT_VERSION=0.37.3
ARG TILT_SHA256=e90bc6cf70882bc7579d8174a27cab2de0284612ec7339e4b32f669cd5de4e5c
ARG CT_VERSION=3.14.0
ARG CT_SHA256=d16f0583616885423826241164ce1f6589c6fe5332fa74f374ebd2bd3cb3fe1f
ARG KUBECONFORM_VERSION=0.6.7
ARG KUBECONFORM_SHA256=95f14e87aa28c09d5941f11bd024c1d02fdc0303ccaa23f61cef67bc92619d73

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
RUN curl -fsSLo /tmp/uv.tar.gz \
        "https://github.com/astral-sh/uv/releases/download/${UV_VERSION}/uv-x86_64-unknown-linux-gnu.tar.gz" \
    && echo "${UV_SHA256}  /tmp/uv.tar.gz" | sha256sum -c - \
    && tar -xzf /tmp/uv.tar.gz -C /usr/local/bin --strip-components=1 \
        uv-x86_64-unknown-linux-gnu/uv \
        uv-x86_64-unknown-linux-gnu/uvx \
    && rm /tmp/uv.tar.gz

# ── Python 3.14 ──────────────────────────────────────────────────────────────
RUN uv python install 3.14

# ── kubectl ──────────────────────────────────────────────────────────────────
RUN curl -fsSLo /usr/local/bin/kubectl \
        "https://dl.k8s.io/release/v${KUBECTL_VERSION}/bin/linux/amd64/kubectl" \
    && echo "${KUBECTL_SHA256}  /usr/local/bin/kubectl" | sha256sum -c - \
    && chmod +x /usr/local/bin/kubectl

# ── k3d ──────────────────────────────────────────────────────────────────────
RUN curl -fsSLo /usr/local/bin/k3d \
        "https://github.com/k3d-io/k3d/releases/download/v${K3D_VERSION}/k3d-linux-amd64" \
    && echo "${K3D_SHA256}  /usr/local/bin/k3d" | sha256sum -c - \
    && chmod +x /usr/local/bin/k3d

# ── Helm ─────────────────────────────────────────────────────────────────────
RUN curl -fsSLo /tmp/helm.tar.gz \
        "https://get.helm.sh/helm-v${HELM_VERSION}-linux-amd64.tar.gz" \
    && echo "${HELM_SHA256}  /tmp/helm.tar.gz" | sha256sum -c - \
    && tar -xzf /tmp/helm.tar.gz -C /tmp linux-amd64/helm \
    && install -m 0755 /tmp/linux-amd64/helm /usr/local/bin/helm \
    && rm -rf /tmp/helm.tar.gz /tmp/linux-amd64

# ── ArgoCD CLI ───────────────────────────────────────────────────────────────
RUN curl -fsSLo /usr/local/bin/argocd \
        "https://github.com/argoproj/argo-cd/releases/download/v${ARGOCD_VERSION}/argocd-linux-amd64" \
    && echo "${ARGOCD_SHA256}  /usr/local/bin/argocd" | sha256sum -c - \
    && chmod +x /usr/local/bin/argocd

# ── Tilt ─────────────────────────────────────────────────────────────────────
RUN curl -fsSLo /tmp/tilt.tar.gz \
        "https://github.com/tilt-dev/tilt/releases/download/v${TILT_VERSION}/tilt.${TILT_VERSION}.linux.x86_64.tar.gz" \
    && echo "${TILT_SHA256}  /tmp/tilt.tar.gz" | sha256sum -c - \
    && tar -xzf /tmp/tilt.tar.gz -C /usr/local/bin tilt \
    && rm /tmp/tilt.tar.gz

# ── chart-testing (ct) ───────────────────────────────────────────────────────
RUN curl -fsSLo /tmp/chart-testing.tar.gz \
        "https://github.com/helm/chart-testing/releases/download/v${CT_VERSION}/chart-testing_${CT_VERSION}_linux_amd64.tar.gz" \
    && echo "${CT_SHA256}  /tmp/chart-testing.tar.gz" | sha256sum -c - \
    && tar -xzf /tmp/chart-testing.tar.gz -C /usr/local/bin ct \
    && rm /tmp/chart-testing.tar.gz

# ── kubeconform ──────────────────────────────────────────────────────────────
RUN curl -fsSLo /tmp/kubeconform.tar.gz \
        "https://github.com/yannh/kubeconform/releases/download/v${KUBECONFORM_VERSION}/kubeconform-linux-amd64.tar.gz" \
    && echo "${KUBECONFORM_SHA256}  /tmp/kubeconform.tar.gz" | sha256sum -c - \
    && tar -xzf /tmp/kubeconform.tar.gz -C /usr/local/bin kubeconform \
    && rm /tmp/kubeconform.tar.gz

# ── Ensure vscode user can use Docker socket (added by docker-outside-of-docker feature) ─
RUN usermod -aG docker vscode 2>/dev/null || true
