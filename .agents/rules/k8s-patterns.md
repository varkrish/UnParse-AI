---
name: k8s-patterns
description: K8s deployment patterns for the agent swarm
alwaysApply: true
---

When writing Kubernetes manifests or Helm templates:

- Use `registry.access.redhat.com/ubi9/python-311:latest` as base image
- Always set `securityContext.runAsNonRoot: true` and `runAsUser: 1001`
- Always include liveness, readiness, and startup probes on /health
- Use resource requests AND limits (agents are I/O bound, keep CPU low)
- Use `app.kubernetes.io/` standard labels: name, component, part-of, version
- PVCs should use default storage class unless explicitly specified
- Secrets must use `stringData` (not base64-encoded `data`) in dev manifests
- Never put real API keys in committed manifests — use placeholders with comments
