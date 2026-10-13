> Publication candidate: adapted from the October 13, 2026 lab snapshot. Historical PASS statements below are not current health or fresh-clone reproduction. Raw evidence, caches and original trust roots are not distributed. See `tools/DEPENDENCIES.md` from the repository root.

> Deployment status: demo restricted admission and GitOps context are applied and proved. CI owns dev/staging/prod workloads and labels. See docs/hardening-report.md.

# PSS exemptions and scope

`demo`, `dev`, `staging`, `prod`: restricted, pinned Kubernetes v1.36. The P6-owned application budgets remain unchanged. New `scen-*` test namespaces are restricted unless a specific dry-run admission test documents an exemption.

Explicit privileged namespace labels:
- `kube-system`: Cilium eBPF/host networking, kube-proxy replacement, node-facing cluster services.
- `longhorn-system`: node block devices, privileged storage engines, host mounts.
- `soc-sensors`: packet capture and node log/audit readers, owned by the parallel SOC worker.
- `falco`: kernel/eBPF runtime sensor requires host mounts and kernel access.
- `audits`: trusted administrator-only kube-bench jobs require hostPID and read-only node mounts. The jobs have no API token.

These exemptions are not an authorization grant: RBAC still restricts who may create Pods. No PSS Enforce restrictions, Kyverno Enforce match, or NetworkPolicy is installed by P5 in SOC or infrastructure namespaces. Other platform/infra namespaces retain their prior (implicit privileged) PSS setting; their application charts were not hardened or restarted by this worker. This is intentional lab scope, not a production posture.

Kyverno enforcement is positively selected by namespace (`demo`, `dev`, `staging`, `prod`, `scen-*`), never by an incomplete exemption blacklist. Registry allowlisting is Audit cluster-wide with a prod-only Enforce override. Signature verification is handed off to P6 in Audit until its key/CA/signing gate passes.

The existing GitOps demo lacked a seccomp profile and an explicit token opt-out. Admission defaults only for `demo` Pods labelled `app=demo` add RuntimeDefault, disable token automount, make nginx's root filesystem read-only and supply narrow emptyDir mounts for `/tmp`, `/var/cache/nginx`, `/var/run`. The explicit context is now synchronized through platform/gitops-seed/app.yaml and local Forgejo lab/gitops, and Argo CD reconciled it. No Argo CD application configuration was changed. The Pod mutation remains narrowly scoped; host-isolation validation uses explicit Deployment-template rules because mixing selector-based mutations with auto-generation was not reliable. Privileged negative tests use a differently labelled fixture, so this mutation cannot hide their result.
