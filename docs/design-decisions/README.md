# Design Decisions

This directory holds lightweight design decision notes for Kate. These are not formal review
records; they are structured notes that preserve useful context for a single-developer project.

## Format

Each decision file uses the same basic structure:

- Title: numbered `Design Decision <id>: <topic>`
- Metadata: status, date, and scope
- Context: problem or constraint being addressed
- Options or rationale: meaningful alternatives and tradeoffs
- Decision: chosen approach
- Consequences: follow-on constraints and operational notes

## Index

| Decision | Summary |
|----------|---------|
| [0001](0001-stack-choices.md) | Platform stack choices |
| [0002](0002-queue-depth-hpa.md) | Worker queue-depth autoscaling |
| [0003](0003-gitops-argocd.md) | ArgoCD app-of-apps and Tilt coexistence |
| [0004](0004-observability-stack.md) | Metrics, logs, traces, and dashboards |
| [0005](0005-chaos-portal.md) | Chaos portal interaction and mutation model |
| [0006](0006-ci-cd.md) | CI/CD quality gates and image publication |
