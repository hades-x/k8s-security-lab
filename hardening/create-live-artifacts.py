
if __name__ == '__main__':
    import os as _runtime_os
    if _runtime_os.environ.get('LAB_ALLOW_RUNTIME') != 'yes':
        raise SystemExit('BLOCKED: runtime requires LAB_ALLOW_RUNTIME=yes and tools/DEPENDENCIES.md review')
from pathlib import Path
import json,yaml
root=Path('/data/k8s-lab')
# All application-token controls remain strict as requested. P6 must explicitly
# disable automount and project a narrowly scoped API token for CNPG if needed.
(root/'evidence/p5/P6-coordination.md').write_text('''# P5 / P6 coordination
- Do not replace P6 quotas, LimitRanges or app NetworkPolicies. P5 scripts now preserve them.
- Kyverno install.sh always includes hardening/kyverno/values.yaml followed by devsecops/kyverno-registry-values.yaml.
- Admission/background/reports controllers still fail: ConfigMap directory is mounted on /etc/ssl/certs/ca-certificates.crt without subPath. P6 owns the CA values fix.
- The strict lab-no-default-token Enforce policy requires automountServiceAccountToken: false for new app Pods. Existing CNPG initdb Pods use serviceAccountName demo-db and currently omit this field. Supply a bounded projected service-account token explicitly for CNPG, or agree a documented least-privilege exception before Enforce.
- P5's signature policy remains Audit; P6 owns the actual key injection and final signature Enforce gate. P5 must not downgrade it after P6 flips it.
- BEFORE evidence collected 12:15-12:16 CEST for kube-bench/NSA/MITRE/Trivy; missing CIS alias was corrected and CIS collected at about 13:08 CEST. Parallel P6 changed the workload inventory in the interval. This is not an isolated causal benchmark.
''')
(root/'tests/phase-p5-hardening.sh').write_text('''#!/usr/bin/env bash
set -euo pipefail
ROOT=$(cd -- "$(dirname -- "${BASH_SOURCE[0]}")/.." && pwd)
source "$ROOT/infra/k3s/env.sh"
python3 -E "$ROOT/hardening/prove.py"
"$ROOT/hardening/rbac/test.sh"
"$ROOT/hardening/netpol/test.sh"
''')
(root/'tests/phase-p5-hardening.sh').chmod(0o755)
(root/'hardening/pss/EXEMPTIONS.md').write_text('''# PSS exemptions and scope

`demo`, `dev`, `staging`, `prod`: restricted, pinned Kubernetes v1.36. The P6-owned application budgets remain unchanged. New `scen-*` test namespaces are restricted unless a specific dry-run admission test documents an exemption.

Explicit privileged namespace labels:
- `kube-system`: Cilium eBPF/host networking, kube-proxy replacement, node-facing cluster services.
- `longhorn-system`: node block devices, privileged storage engines, host mounts.
- `soc-sensors`: packet capture and node log/audit readers, owned by the parallel SOC worker.
- `falco`: kernel/eBPF runtime sensor requires host mounts and kernel access.
- `audits`: trusted administrator-only kube-bench jobs require hostPID and read-only node mounts. The jobs have no API token.

These exemptions are not an authorization grant: RBAC still restricts who may create Pods. No PSS Enforce restrictions, Kyverno Enforce match, or NetworkPolicy is installed by P5 in SOC or infrastructure namespaces. Other platform/infra namespaces retain their prior (implicit privileged) PSS setting; their application charts were not hardened or restarted by this worker. This is intentional lab scope, not a production posture.

Kyverno enforcement is positively selected by namespace (`demo`, `dev`, `staging`, `prod`, `scen-*`), never by an incomplete exemption blacklist. Registry allowlisting is Audit cluster-wide with a prod-only Enforce override. Signature verification is handed off to P6 in Audit until its key/CA/signing gate passes.

The existing GitOps demo lacked a seccomp profile and an explicit token opt-out. Admission defaults only for `demo` Pods labelled `app=demo` add RuntimeDefault, disable token automount, make nginx's root filesystem read-only and supply narrow emptyDir mounts for `/tmp`, `/var/cache/nginx`, `/var/run`. No Forgejo commit or Argo CD configuration edit is made. The matching mutation is auto-generated for Deployment admissions as well. Privileged negative tests use a differently labelled fixture, so this mutation cannot hide their result.
''')
print('Created repeatable acceptance entry point and explicit PSS/P6 coordination documents.')
