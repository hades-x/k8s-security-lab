> Publication candidate: adapted from the October 13, 2026 lab snapshot. Historical PASS statements below are not current health or fresh-clone reproduction. Raw evidence, caches and original trust roots are not distributed. See `tools/DEPENDENCIES.md` from the repository root.

# Bounded audit snapshots

Use `source infra/k3s/env.sh` from `/data/k8s-lab`.

- `python3 audits/collect-safe.py kube-bench`: sequential administrator-only Jobs
  on lab-s3 and lab-a1. k3s-cis-1.9 is the available profile; it does not
  certify Kubernetes 1.36. Missing journalctl causes measurement failures.
- `python3 audits/collect-safe.py kubescape`: host CLI NSA/MITRE/CIS v1.12.0;
  six namespaces, no host collector, keep-local, cached frameworks, bounded
  timeouts. Reconstructs paired before/after demo seed files, never live rollback.
- Trivy chart 0.37.0/app 0.35.0/scanner 0.75.0 is configured for six namespaces,
  one concurrent scan Job and a two-Pod quota (one operator plus one scanner).
  Controller/scanner limits are 512Mi. It stays scaled to zero between audits.
  Config and RBAC reports were collected; **fresh vulnerability coverage failed
  on local registry TLS trust**, after an API-interrupted first attempt. No TLS
  bypass or fabricated CVE result is acceptable.
- `run-before.sh` refuses to overwrite historical evidence. `run-after.sh` uses
  bounded collectors and requires explicit reviewed-CA confirmation before Trivy.
- `python3 audits/summarize.py evidence/p5/after` records passing Trivy checks as
  N/A because reports store failed checks only. `audits/compare.sh` writes
  `docs/hardening-report.md` and `evidence/p5/comparison.md` with partial-baseline
  boundaries, matched file-only deltas, exclusions and stale-report limitations.

Host available RAM must remain above 4 GiB. Save resource samples and check real
scanner concurrency. Scanner Jobs run in trivy-system, not in application
namespaces; do not broaden application egress. Read-only cluster-RBAC reports
are inherently cluster-scoped. No Secret values are collected or printed.
