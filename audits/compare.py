#!/usr/bin/env python3

if __name__ == '__main__':
    import os as _runtime_os
    if _runtime_os.environ.get('LAB_ALLOW_RUNTIME') != 'yes':
        raise SystemExit('BLOCKED: runtime requires LAB_ALLOW_RUNTIME=yes and tools/DEPENDENCIES.md review')
"""Generate an honest report: partial history, paired seed files, live after."""
import datetime
import json
from pathlib import Path
import sys

root = Path(sys.argv[1])
repo = root.parents[1]
after = json.loads((root / 'after/summary.json').read_text())

def load(path):
    text = path.read_text()
    return json.loads(text[text.index('{'):])

def controls(path):
    d = load(path)['summaryDetails']['controls']
    return list(d.values()) if isinstance(d, dict) else d

def status(control):
    s = control.get('status')
    return str(s.get('status') if isinstance(s, dict) else s).lower()

print('# P5 defensive hardening report\n')
print('Generated: ' + datetime.datetime.now().astimezone().isoformat() + '\n')
print('## Acceptance\n')
proofs = json.loads((root / 'proof-results.json').read_text())
rbac = json.loads((root / 'rbac/impersonation-results.json').read_text())
print('| Item | Result | Evidence |\n|---|---|---|')
print(f"| Admission, encryption and dataplane | {'PASS' if all(x['pass'] for x in proofs) else 'FAIL'}: {sum(x['pass'] for x in proofs)}/{len(proofs)} | `evidence/p5/test-hardening.log`, `proof-results.json` |")
print(f"| Minimal RBAC | {'PASS' if all(x['pass'] for x in rbac) else 'FAIL'}: {sum(x['pass'] for x in rbac)}/{len(rbac)} | `evidence/p5/rbac/impersonation-results.json` |")
print('| kube-bench collection | PASS: one server and one agent Job completed, sequentially | `evidence/p5/after/kube-bench-execution.json` |')
print('| Kubescape collection | PASS: NSA, MITRE, CIS v1.12.0; degraded coverage, not a compliance certification | `evidence/p5/after/kubescape-*.json` |')
config = after['trivy-configauditreports']
print(f"| Trivy configuration audit | PASS: {config['reports']} reports in six namespaces | `evidence/p5/after/trivy-configauditreports.json` |")
print('| Fresh Trivy vulnerability audit | FAIL: local Zot CA is not trusted by the scanner; only a stale historical report remains | `evidence/p5/after/trivy-operator-last.log`, `trivy-vulnerability-freshness.json` |')
print('| Audit shutdown | PASS: Trivy desired replicas returned to 0; scanner Jobs removed | `evidence/p5/after/trivy-deployment-stopped.json` |\n')
print('## Before/after: evidence boundaries\n')
print('**A complete pre-hardening baseline was not captured.** The handed-off reliable baseline is the kube-bench agent output. Additional earlier files were discovered in `before/` and retained, but their completeness and inventory pairing were not established; they are not promoted into a complete baseline or used for causal deltas. See `evidence/p5/before-provenance-inventory.json`. No live policy was weakened or rolled back to reconstruct a before state.\n')
print('### Comparable reconstruction: original GitOps demo seed\n')
print('The before input is the exact `git show p4:platform/gitops-seed/app.yaml`; the after input is the updated seed synchronized to Forgejo. Both contain the same PVC, Deployment, Service and Ingress. These are **file-only scans of the demo seed**, not historical cluster snapshots. Control IDs are checked for equality below. Both runs use the same cached framework files and report 90% coverage with fallback policy inputs; the remaining findings are retained.\n')
print('| Framework | Before pass/fail | After pass/fail | Failed-control delta | Reported score before/after |\n|---|---:|---:|---:|---:|')
b = json.loads((root / 'reconstructed-before/summary.json').read_text())
a = json.loads((root / 'reconstructed-after/summary.json').read_text())
repaired_sets = []
for name in sorted(b):
    label = name.removeprefix('kubescape-')
    bc = controls(root / 'reconstructed-before' / ('kubescape-' + label + '.json'))
    ac = controls(root / 'reconstructed-after' / ('kubescape-' + label + '.json'))
    assert {x['controlID'] for x in bc} == {x['controlID'] for x in ac}, 'Unpaired control inventory: ' + name
    print(f"| {name} | {b[name]['pass']}/{b[name]['fail']} | {a[name]['pass']}/{a[name]['fail']} | {a[name]['fail']-b[name]['fail']:+d} | {b[name]['compliance_score']}/{a[name]['compliance_score']} |")
    repaired = sorted({x['controlID'] for x in bc if status(x) == 'failed'} - {x['controlID'] for x in ac if status(x) == 'failed'})
    if repaired:
        repaired_sets.append(name + ': ' + ', '.join(repaired))
print('\nImproved control IDs: ' + '; '.join(repaired_sets) + '.\n')
print('\nThe reconstruction improves NSA immutable filesystem, token automount and Linux hardening controls, and CIS token automount/seccomp controls. MITRE is unchanged. The seed-only NSA network isolation check remains failed because NetworkPolicies are installed separately rather than included in the seed. Non-root/security-context controls also remain flagged; the Pod-level context is not claimed to satisfy every scanner-specific container check.\n')
print('### Live after snapshot (not fully paired with before)\n')
print('| Tool / unit | Reliable before pass/fail | After pass/fail | After reports / notes |\n|---|---:|---:|---|')
agent = load(root / 'before/kube-bench-agent.json')
ct = agent.get('Controls', agent.get('controls', []))
trusted = {k: sum(int(x.get('total_' + k, 0)) for x in ct) for k in ['pass', 'fail']}
for name in sorted(after):
    row = after[name]
    prior = f"{trusted['pass']}/{trusted['fail']}" if name == 'kube-bench-agent' else 'N/A (partial before)'
    passed = 'N/A' if row.get('pass') is None else str(row['pass'])
    note = str(row.get('reports', ''))
    if 'warn' in row:
        note = f"{row['warn']} WARN, {row['info']} INFO"
    if 'scan_coverage' in row:
        cov = row['scan_coverage']
        note = f"{row['excluded']} excluded; coverage {cov.get('coverageScore')}%; {cov.get('evaluatedControls')}/{cov.get('totalControls')} evaluated"
    if name == 'trivy-vulnerabilityreports':
        note += '; stale, not fresh-after coverage'
    print(f"| {name} | {prior} | {passed}/{row['fail']} | {note} |")
print('\nTrivy CVE counts, failed configuration checks, RBAC checks and Kyverno policy results are different units. Trivy stores failed checks only; passing-check totals are **N/A**, not zero. Expanded inventories are not evidence that hardening caused an increase or decrease. The app-only Trivy high/critical count covers demo/dev/staging/prod, not all six target namespaces.\n')
print('## Resource budget and audit coverage\n')
samples = json.loads((root / 'after/resource-samples.json').read_text())
extra = json.loads((root / 'after/kube-bench-execution.json').read_text())
ks = json.loads((root / 'after/kubescape-execution.json').read_text())
minimum = min(x['availableKiB'] for x in samples + extra + ks)
print(f"Host available RAM minimum across saved audit samples: **{minimum / 1024 / 1024:.2f} GiB** (>4 GiB). The bounded collector stops below the threshold. Node CPU/memory readings are saved per sample; high node loads during the API incident are captured separately in `recurring-api-incident.json`.\n")
print(f"Trivy's configured scan-job limit is 1. The first attempt nevertheless created two simultaneous init Pods; a namespace ResourceQuota of two nonterminated Pods (operator plus one scanner) was then added. The second attempt observed at most **{max(x.get('activeScannerPods', 0) for x in samples)} scanner Pod**. Trivy is scoped to `demo,dev,staging,prod,argocd,forgejo`; cluster-RBAC assessments are read-only and cluster-scoped by definition. Scanner and controller requests/limits remain bounded, and all scan Jobs were removed at shutdown.\n")
print('Kubescape runs on the host with `--keep-local --host-scan=false`, six included namespaces, cached NSA/MITRE/CIS v1.12.0 frameworks and bounded scan/control timeouts. kube-system, SOC, Falco and Longhorn workload audits are deliberately outside this namespace scope. CIS v1.12.0 was available locally; it was used instead of requested v1.10.0. kube-bench uses the available k3s-cis-1.9 profile, not a newly asserted certification for Kubernetes 1.36.\n')
print('## What did not improve, and why\n')
print('- kube-bench agent findings are unchanged. Node defaults/filesystem permissions were not modified in this scope. Several server FAILs and the agent read-only-port FAIL are **measurement failures** (`journalctl: not found` in the scanner image), not proven unsafe flag settings. Manual WARNs remain; inspect raw reasons before remediation. Host journals/binaries were not mounted or host packages installed to make scores look better.')
print('- Kubescape coverage is degraded by disabled/unsupported CLI host collection, absent cloud-provider inputs and fallback control/exception data. Live scores are not comprehensive CIS compliance and are not causal before/after comparisons.')
print('- Configuration/RBAC findings persist in platform charts and the wider read-only cluster inventory. Existing named API clients retain required tokens; the default-service-account token policy does not remove tokens from named CNPG clients. Developers can select service accounts or create Pods referencing Secrets, so absence of direct Secret GET does not prove absence of indirect Secret access.')
print('- Sensor/storage/system exemptions remain: SOC capture and log readers, Falco eBPF/kernel access, Longhorn host mounts/devices, kube-system node-facing services, and administrator-only kube-bench hostPID/read-only host mounts in audits. These are not RBAC grants. This worker did not alter SOC namespaces or dev/staging/prod workloads.')
print('- The first Trivy collection failed during recurring API VIP interruption; direct server endpoints were used for read-only audits afterwards. The second reached image scanning but failed against the local Zot registry with `x509: certificate signed by unknown authority`. After two failed attempts it was stopped, without disabling TLS verification, changing the registry, or inventing CVE results. The stale demo report belongs to the old ReplicaSet and is not accepted as a fresh audit.')
print('- Kyverno controllers and the API were intermittently unavailable during collection. A later full `tests/phase-p5-hardening.sh` run via the normal VIP succeeded, but this is a point-in-time acceptance result, not a sustained API-availability claim.\n')
print('## RBAC and enforced scope\n')
secret = json.loads((root / 'after/rbac/secret-readers.json').read_text())
sars = json.loads((root / 'after/rbac/secret-reader-sar.json').read_text())
print(f"Secret-reader audit: **{len(secret)} binding/subject/rule rows**, **{len(sars)} concrete SAR rows**, **{sum(x['answer']=='yes' for x in sars)} positive SAR rows**. Rows are not necessarily distinct principals. Group membership is not expanded automatically; the three training groups are separately proved with `--as` plus `--as-group`. No Secret values are read or retained.\n")
print('Viewer and SOC analyst can read Pods/logs in dev/staging; developers additionally patch Deployments there. All three are denied direct Secret reads, RoleBinding creation and Pod exec, and have no tested prod access. These bindings do not grant the SOC-named training role access to SOC infrastructure namespaces. See `hardening/README.md` for the control → mechanism → scope → proof table.\n')
print('## Reproduction\n')
print('```bash\ncd /data/k8s-lab\nsource infra/k3s/env.sh\ntests/phase-p5-hardening.sh\npython3 audits/collect-safe.py kube-bench\npython3 audits/collect-safe.py kubescape\n# Trivy remains paused. Resolve registry CA trust before a separately approved retry:\n# python3 audits/collect-safe.py trivy\npython3 audits/summarize.py evidence/p5/after\naudits/compare.sh\n```')
