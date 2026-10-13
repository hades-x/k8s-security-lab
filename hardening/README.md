> Publication candidate: adapted from the October 13, 2026 lab snapshot. Historical PASS statements below are not current health or fresh-clone reproduction. Raw evidence, caches and original trust roots are not distributed. See `tools/DEPENDENCIES.md` from the repository root.

# P5 defensive baseline

Live acceptance: `tests/phase-p5-hardening.sh` (exit 0 recorded in
`evidence/p5/test-hardening.exit`). Raw audit findings and incomplete coverage are
reported in `docs/hardening-report.md`; passing admission tests are not CIS certification.

| Control | Mechanism | Enforced scope | Proof file (under evidence/p5/) |
|---|---|---|---|
| Restricted Pods | Kubernetes Pod Security Admission, pinned v1.36 | demo; dev/staging/prod labels are managed by the CI worker | demo-namespace.json; negative-privileged-pss.log |
| Privileged containers, hostPath, hostNetwork | Kyverno lab-host-isolation, Enforce; explicit Pod and Deployment-template rules | demo, dev, staging, prod, scen-* | live-host-isolation-policy.json; negative-privileged-kyverno.log |
| CPU/memory requests and limits | Kyverno lab-resource-budget, Enforce; demo also has defaulting LimitRanges | Same application/test scope | negative-limits.log (isolated P5 target namespace without a LimitRange) |
| No latest/implicit image tags | Kyverno lab-image-tags, Enforce | Same application/test scope | negative-latest.log |
| No default API token | Kyverno lab-no-default-token, Enforce | Default-service-account Pods in the same scope; named API clients exempt | negative-token.log |
| Demo filesystem/context | Declarative GitOps seed plus narrow admission defaults | demo app=demo; read-only root, RuntimeDefault, token opt-out, narrow writable emptyDirs | demo-gitops-sync.log; demo-live-state.json; demo-http.log |
| Registry allowlist | Kyverno Audit; prod-only Enforce override | Audit cluster-wide, Enforce prod | live-cluster-policies.json |
| Network isolation | Cilium/Kubernetes default deny, explicit DNS/app-db/ingress/metrics allows; quarantine deny override | demo/dev/staging/prod policy objects; live dataplane exercised in demo | allowed-flows.log; blocked-flow.log; hubble-dropped.jsonl; prometheus-allowed.json |
| Least-privilege training roles | RoleBindings for lab-viewer, lab-dev, soc-analyst | dev/staging; tested prod access denied | rbac/impersonation-results.json (57 checks); after/rbac/secret-readers.json |
| Secrets at rest | k3s AES-CBC encryption, enabled at cluster creation | Kubernetes Secrets; dummy value checked in server s2 etcd | etcd-encryption.log |

## Re-run safely

```bash
cd /data/k8s-lab
source infra/k3s/env.sh
tests/phase-p5-hardening.sh
python3 audits/collect-safe.py kube-bench
python3 audits/collect-safe.py kubescape
python3 audits/summarize.py evidence/p5/after
audits/compare.sh
```

- `MODE=Enforce hardening/kyverno/apply-policies.sh` reapplies the four baseline
  validation policies. Signature verification belongs to P6 and is not proved here.
- For **any Kyverno Helm upgrade**, pass `-f hardening/kyverno/values.yaml`
  **then** `-f devsecops/kyverno-registry-values.yaml`; never omit either file.
- The demo's explicit security context is synchronized from
  `platform/gitops-seed/app.yaml` into local Forgejo `lab/gitops`; Argo CD reconciles it.
- Trivy stays paused (`operator.replicas: 0`). Collection briefly ran one controller,
  configured one scan Job, and added a two-Pod quota to serialize real scanner Pods.
  Targets: demo/dev/staging/prod/argocd/forgejo. Configuration reports were collected;
  **fresh vulnerability coverage failed because the local registry CA is untrusted**.
  Resolve CA trust before a separately approved retry; do not disable TLS verification.
- No complete before baseline exists. The report distinguishes the preserved partial
  history from matched file-only scans of the p4 and current demo seeds; no live
  policies are rolled back. No SOC namespace or CI workload was modified by this worker.

PSS/host-access exemptions for system services, Longhorn, SOC sensors, Falco and
trusted kube-bench Jobs are documented in `pss/EXEMPTIONS.md`. No direct Secret GET
permission does **not** prevent indirect access through workload creation or named
service-account selection; see the secrets-reader audit and report limitations.
