> Publication candidate: adapted from the October 13, 2026 lab snapshot. Historical PASS statements below are not current health or fresh-clone reproduction. Raw evidence, caches and original trust roots are not distributed. See `tools/DEPENDENCIES.md` from the repository root.

# Pod Security Standards
Application and normal scenario namespaces enforce restricted v1.36 immediately. This is independent of Kyverno Audit mode.
Privileged exemptions (not admission-config exemptions): kube-system/Cilium for CNI and node plumbing; longhorn-system for CSI/host storage; soc-sensors for Zeek packet capture; falco for kernel/eBPF sensor; audits for read-only host inspection; scenario-s3-audit for the explicit sacrificial S3 exercise only. All audit/warn restricted.
Baseline: argocd, forgejo, kafka, opensearch, misp, kyverno, trivy-system, zot, monitoring, scenario-infra. These avoid breaking upstream charts while retaining host isolation; inspect warnings before tightening. Cilium in kube-system inherits its exemption; a separate cilium namespace is covered explicitly.
Never grant users namespace label mutation. Restrict the sacrificial namespace to administrators, use a designated disposable node, and delete the pod after the run. PSS is namespace-wide, not per-pod.
Run install.sh then test.sh on the lab only. Test uses server dry-run and requires a specific PodSecurity denial, not any generic error.
