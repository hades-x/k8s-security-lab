> Publication candidate: adapted from the October 13, 2026 lab snapshot. Historical PASS statements below are not current health or fresh-clone reproduction. Raw evidence, caches and original trust roots are not distributed. See `tools/DEPENDENCIES.md` from the repository root.

# P6 — signed orders CI/CD lab

## Verified result (October 13, 2026)

`tests/phase-p6.sh` exited **0**. The full evidence is `evidence/p6/test-run.log`.
A real `git push` of commit `0c49a685f92a236975b031a1b1de7258dc27cce5`
triggered Woodpecker pipeline **9**, without webhook replay or manual pipeline start:

```text
Forgejo git push -> Woodpecker native push webhook
 -> six domain unit tests
 -> Kaniko daemonless build (Docker tar for scan + OCI layout for publication)
 -> Trivy gate (fixed CRITICAL vulnerabilities; exit 1 blocks publication)
 -> zot push -> Cosign sign + verify
 -> Git commit of immutable digest in values-dev.yaml
 -> Argo CD automated sync -> three Ready app pods on the new digest
 -> separate staging/prod Git promotions -> automated sync
```

All three Argo Applications are **Synced / Healthy**. Their final app image is:

```text
zot.192.168.150.200.sslip.io/lab/demo-app@sha256:c8ca54a5ff3ffe83b2a7b78f157cb8ac0b035e255b70bd23c4cbdabcfaa7f7d1
```

Staging promotion: `98d8b18c9d4e3caec4e21b34f3a664d4de852c17`.
Prod promotion: `8fa0c7979ba77a468499da017ce40422a4895c39`.
These are Git commits in **in-cluster Forgejo**, not commits in the orchestration
repository `/data/k8s-lab`. The orchestration repository remains uncommitted for
its owner to review.

## Three-minute demo

Run on lab controller; open the corresponding app/CI UI if desired. This short demo
reuses the recorded build instead of promising a full build in three minutes.

```bash
export LC_ALL=C
cd /data/k8s-lab
source infra/k3s/env.sh

# 0:00 — show the successful actual push and each CI gate.
python3 - <<'PY'
import json
from pathlib import Path
p=json.loads(Path('evidence/p6/acceptance-pipeline.json').read_text())
print('pipeline',p['number'],'commit',p['commit'],'status',p['status'])
for w in p['workflows']:
    for s in w['children']:
        print(s['name'],s['state'],'exit',s['exit_code'])
PY

# 0:30 — live, read-only checks: three GitOps apps, imageIDs and databases.
tests/phase-p6.sh --read-only

# 1:00 — actually admit a signed Pod, reject an unsigned zot image,
# then POST -> PostgreSQL -> Kafka record -> worker -> Valkey -> GET.
# It creates synthetic data and removes only its temporary proof Pods.
tests/phase-p6.sh --demo

# 2:30 — show direct persisted evidence, not only HTTP status.
python3 - <<'PY'
import json
from pathlib import Path
p=json.loads(Path('evidence/p6/e2e-dev.json').read_text())
print('order',p['post']['id'])
print('Postgres',p['postgresRow'])
print('Kafka',p['kafka']['topic'],p['kafka']['partition'],p['kafka']['offset'])
print('Valkey',p['valkey'])
print('GET cached=',p['get']['cached'])
PY
```

Browser hostnames: `ci.192.168.150.200.sslip.io`,
`orders-dev.192.168.150.200.sslip.io`, `orders-staging.192.168.150.200.sslip.io`,
`orders-prod.192.168.150.200.sslip.io`. HTTPS uses the lab root CA; import the
public root into the browser if needed. Do not disable certificate verification.

## Re-run full acceptance

```bash
export LC_ALL=C
cd /data/k8s-lab
source infra/k3s/env.sh
set -o pipefail
tests/phase-p6.sh 2>&1 | tee evidence/p6/test-run.log
```

This is a mutating lab test. It creates a real commit in a private isolated
Forgejo clone under `.secrets/p6/git-triggers/`, pushes it to `lab/demo-app`,
waits for its matching automatic Woodpecker pipeline, verifies the signature
and legacy signature artifact, promotes that same digest by Git to staging
and prod, verifies all running container imageIDs, tests positive/negative
prod admission, and creates one synthetic dev order. Polling is bounded to
600 seconds per major phase; CI capacity is one. A lock prevents concurrent
acceptance runs. `--read-only` performs no cluster/Git/data mutations; local
non-secret evidence may be refreshed. `--demo` repeats runtime admission and
data-flow checks without starting another build.

Additional direct integration checks:

```bash
python3 devsecops/acceptance.py --e2e --environment staging --timeout 120
python3 devsecops/acceptance.py --e2e --environment prod --timeout 120
```

## Recovery changes and why

| Failure observed | Verified correction |
|---|---|
| Publisher exit 137 under a 256Mi limit | 768Mi publisher limit within the unchanged 1536Mi CI quota; stream tool downloads instead of buffering a full compressed archive. |
| Temporary gRPC JWT signing secret on restart | Persist `WOODPECKER_GRPC_SECRET` in `.secrets/p6/woodpecker-grpc-secret` and an opaque Kubernetes Secret; chart references it with `envFrom`. Server and agent were restarted again before pipelines 8/9 passed. Never print the key. |
| CNPG initdb API requests timed out under default-deny | Per-environment Cilium policies select only `cnpg.io/cluster=demo-db` and allow `toEntities: kube-apiserver`, TCP 443/6443. Delete/retry only the exhausted initdb Job, preserve PVC and secrets. |
| App image had an all-zero placeholder digest | CI now publishes/signs first and commits a real digest; Argo replaces the failed Pods. No imperative app image patch. |
| Bad Kyverno CA ConfigMap-directory volume | Installer emits `global.caCertificates.data`, not the broken volume overlay. Shared Helm upgrade is opt-in (`--upgrade`) and always includes both hardening and P6 values overlays. No healthy shared Kyverno deployment was patched during this recovery. |
| zot rejected Docker manifest reconstructed from Kaniko tar | Publish Kaniko's OCI layout directly with `crane push image-oci`; Trivy still scans the same build's Docker tar. Assert published digest equals Kaniko's digest. |
| Signed private-key image tried downloading public SCT roots | Private-key lab attestor sets both `rekor.ignoreTlog` and `ctlog.ignoreSCT`. Public-key signature validation and digest checks remain required. |
| Cosign verify passed, but Kyverno said no signatures found | Cosign 3.1.3 signer explicitly uses `--new-bundle-format=false` plus legacy referrers; prove the `sha256-<digest>.sig` artifact exists. Re-sign the three prerequisite images. |
| CNPG recreated prod primary every few seconds | Pin both operator image and expected `OPERATOR_IMAGE_NAME` to the same signed tag+digest before Kyverno mutation. No exception or relaxed admission policy. |
| Prod ACME solver was unsigned | Prod uses the **existing** `lab-ca` ClusterIssuer via a Git chart change, avoiding a solver Pod. Dev/staging retain `lab-acme`. No unsigned-image exemption. |
| Rapid mirror plus trigger commits superseded one another | A changed source mirror is itself the single native trigger; no second duplicate push. Full acceptance uses an actual isolated Git clone/commit/push. |

`devsecops/test-recovery.py` covers seven recovery contracts. RED failures and
GREEN runs are preserved in numbered evidence logs. Historical failures are
retained for learning, not presented as successful runs.

For the already bootstrapped lab, reconcile owned recovery objects with
`devsecops/install.sh`. The older `app-create.py` is an initial source generator,
not a recovery command: do not run it over the tested chart/source because it
resets initial placeholders. `publish-repos.py` publishes owned source to the
lab's Forgejo and can trigger a build; never run it concurrently with acceptance.

## Resource and security boundaries

- P6 namespace quota maxima: CI 1536Mi plus dev/staging/prod 1024Mi each.
  CNPG operator limit: 192Mi. Combined maximum: **4800Mi = 4.6875GiB**,
  below the 5GiB budget. Shared Forgejo, Argo, zot, Kafka and Kyverno are
  pre-existing platform components, not silently counted as P6 workloads.
- One CNPG instance per environment, 256Mi each; three 96Mi app processes and
  64Mi Valkey per environment. Quotas include init/build containers. CI runs
  one workflow at a time and build Pods are pinned to agent node a1.
- Before and during tests, stop if host available memory is <=4GiB or a node
  is not Ready / has MemoryPressure, DiskPressure or PIDPressure. Final
  recorded host availability remained above 4GiB. See resource evidence.
- Secrets stay in `.secrets/` or Kubernetes/Woodpecker secrets. Evidence contains
  identifiers, digests, synthetic orders and public certificates, not passwords
  or private keys. No credentials in Git URLs or command arguments.
- Prod policy `lab-prod-signatures` is **Enforce** for every Pod image, including
  init containers; signed image admitted/Running, unsigned image denied with
  `no signatures found`. No other Kyverno policy was edited.
- No unrelated workloads VM, host firewall/network/sysctl/package state, or unrelated SOC
  workload was modified. Only the existing demo topic/user are consumed.

## Lab limitations / not claimed

No production-readiness, keyless identity, public transparency-log guarantee,
transactional outbox, exactly-once delivery, HTTP authentication, DB HA or
persistent Valkey cache is claimed. Single-instance DBs use lab local storage;
cache TTL is 24 hours. Kafka publish can fail after DB commit (503 with an id).
Trivy blocks **fixed CRITICAL** vulnerabilities; HIGH and unfixed CRITICAL findings
are not a passing security assertion. Promotion uses direct Git commits, not a
required PR approval workflow. A transient API connection reset was recorded
during initial prod rollout; the later complete acceptance and read-only checks
passed, but this is not a long-term stability or performance qualification.

Cosign's legacy format flags are compatibility debt. A future migration should
use a jointly tested Kyverno SigstoreBundle policy and modern bundle format;
do not remove compatibility flags without re-running positive and negative
admission tests. This lab deliberately avoids public Rekor/SCT dependencies.

## Evidence index

- `test-run.log`: final actual git push, pipeline 9, Git promotions, all three
  envs Healthy, signed/unsigned admission and dev integration, exit 0.
- `acceptance-pipeline.json`, `ci-9-*.log`: matching commit and five successful steps.
- `acceptance-signature-manifest.json`, `acceptance-cosign.json`: artifact and verification.
- `argocd-{dev,staging,prod}-proof.json`: Git revisions and actual runtime imageIDs.
- `promotion-{staging,prod}.json`: promotion Git commit ids and exact digest.
- `admission-proof.json`, `unsigned-prod-rejection.log`: positive/negative admission.
- `e2e-{dev,staging,prod}.json`: same order matched across SQL, Kafka offset,
  worker record, Valkey and HTTP response.
- `resource-audit.json`, `final-runtime.log`: budget, UID stability, nodes/load,
  database readiness, final source validation and read-only test.
