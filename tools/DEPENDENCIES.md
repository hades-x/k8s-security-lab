# Preserved implementation and operator prerequisites

`make ci` is the supported default. It uses Python 3 standard library, Bash and Make only. It performs AST parsing (not imports) of all Python files, Bash syntax parsing (not execution), JSON/NDJSON parsing, seven explicitly reviewed offline unittest suites, and the all-file public audit. No package installation, Docker, Kubernetes, SSH, libvirt, remote Git or downloads occur in this gate. Supported verification baseline: Python 3.13 on Linux; CI uses the Python supplied by Ubuntu 24.04. A hosted CI run is not yet a verified result.

## Safety boundary

Runtime shell entrypoints refuse before changing HOME, creating directories or contacting services unless `LAB_ALLOW_RUNTIME=yes`. Runtime Python command entrypoints are similarly gated, except the application service and domain code, offline tests/predicates, fixture exporter, and scenario runner (which has its own two authorization checks). **Do not import arbitrary runtime Python scripts:** many old operational helpers execute at import time. Guards are accidental-execution prevention, not a sandbox. Acceptance scripts are not discovered or automatically run by CI.

`make test` now means offline checks. `make smoke` is the old live read-only smoke suite, separately authorized. `make status`/`status-quick` still provide controller-specific status for exercise preflights but are runtime-gated. The original `make start`, `stop` and credential-display paths are blocked. Original unrelated-VM orchestration, disk repair, broker-data reset and index-loss recovery scripts are not distributed.

## Disabled historical automation

The scenario action functions and wrappers, `scenarios/run-all.sh`, all four exercise run/cleanup scripts, common/snapshot shell libraries, and the native Security Analytics importer are **unconditionally disabled**, even with `LAB_ALLOW_RUNTIME=yes`. Pure predicates, manifest builders, reporting functions, offline tests and manifests remain usable for study. This is deliberate fail-closed packaging, not a working automatic lab recreation.

Code review found scenario namespace discovery could treat any failed GET as absence and then apply; cleanup could treat failed read-back as successful absence; `detect` performed SIEM writes without the trigger flag. Exercise ownership used a common label rather than an exact UID/run; snapshot cleanup could delete every matching prefix under a coarse marker. Native import currently has 18 rules but missing input for the added rule before old 17-rule assertions. These paths need isolated negative/concurrency tests and adaptation before reactivation. No environment variable bypass is provided for them. See [disabled paths](RUNTIME_DISABLED.md).

## Dependency map: what a fresh clone does not supply

| Consumer | Missing input | Required operator work |
|---|---|---|
| Most runtime scripts | `/data/k8s-lab`, `bin/`, `.secrets/kubeconfig`, VM SSH key, known hosts, five nodes | Review source, provision a disposable controller/cluster and correctly scoped credentials; numerous absolute paths remain. No portable install is claimed. |
| `infra/libvirt/up.sh`, `network.xml` | Physical uplink, libvirt tooling, cloud image availability | Replace `REPLACE_WITH_LAB_UPLINK`, inspect subnet overlap and host capacity. Lab node names are synthetic `lab-s1..s3`, `lab-a1..a2`. Default new disks use `cache=none`, not the original unsafe cache. Original RAM expectation tests and provisioning sizes need reconciliation. |
| `infra/k3s/install.sh` | Excluded upstream `install-k3s.sh` | Fetch the pinned release installer from official upstream; verify `install-k3s.sha256` before executing. Bundled upstream source was excluded, not relicensed. |
| Ingress/PKI installers | Excluded Gateway API standard CRD bundle | Fetch the exact release asset from `VERSIONS`; verify the recorded SHA-256. Both old bundle paths remain explicit missing prerequisites. |
| P3 installers and `tests/phase-p3.sh --static` | `evidence/p3-prep/` chart caches, preparation generators, CRD schemas | Rebuild version-locked charts and preparation inputs independently. The private evidence-based refresh/static workflow is **not included** and is not part of `make ci`. |
| PKI, registry/OIDC, Kyverno/trivy trust | Original PEM/base64 CA roots and signing public keys removed | Generate a new root/intermediate and Cosign key pair; keep private material out of Git; render every `REGENERATE_LAB_*` template and update both registry values overlays, CA bundles and signature policies. Paths in `ca.json` are stock container paths, not operator homes. Do not deploy placeholder values or reuse old digest signatures. |
| `app/ci`, pipeline generator | New `hardening/kyverno/cosign.pub`, per-step runtime authorization, CI secrets | Provide your own generated key/trust and CI secrets; inject `LAB_ALLOW_RUNTIME=yes` in explicitly approved Woodpecker runtime steps. Existing private-registry image digests are historical artifacts, not downloadable public app images. Rebuild/mirror/sign/promote under your own registry. |
| Audit collectors | Omitted Kubescape frameworks, old before/after baselines | Fetch upstream frameworks for your pinned version and create fresh baselines. Missing historical data cannot produce valid comparisons. Audit collectors may create Jobs and have privileged host mounts. |
| Smoke/scenario monitor checks | `evidence/p4/alerting-state.json` with deployment-generated IDs | Run a freshly reviewed `soc/detection/install-alerting.py` on the disposable lab. Missing registry fails with an explicit prerequisite before the smoke tunnel opens. Never ship old runtime IDs. |
| Dashboard importer | Generated dashboard NDJSON and live field metadata exports excluded | The retained `soc/opensearch/dashboards/import.py` builds its six panels and regenerates its own operator-local exports; no raw saved-object state is shipped. |
| SOC render/validate/offline tooling | `bin/vector`, Helm caches, release schemas, `.venv-sigma`, Scapy | Provision isolated checksum-verified tools and dependencies. Their original “offline” validators can download schemas or use caches; they are **not** the public stdlib offline gate. |
| Scenario monitors/Sigma import | 18 rule files versus older importers' 17-rule assertions | Reconcile the count/mapping before a native re-import. The added forbidden-Secret case is handled by scenario fallback; no full fresh native import is claimed. |
| Exercise report verifier | Raw run logs, private decision/report files, kubeconform output | Execute only on an authorized lab after reviewing each FICHE. Historical private evidence is excluded. The report generator is runtime-gated and must not manufacture a new PASS. |

The CIDRs `192.168.150.0/24`, `10.42.0.0/16`, `10.43.0.0/16`, static lab-only VIPs, and synthetic `*.lab.test` indicators are coherent isolated examples. Existing sslip.io ingress contracts are preserved, not rewritten in ways that would break TLS/SNI/DNS. These addresses must not be treated as available targets outside an operator-owned disposable lab.

## What is actually preserved

The orders application, chart and unit tests; platform/service manifests and pinned versions; SOC pipeline, detection rules/queries/monitors and synthetic exporters; hardening policies and bounded auditing code; namespace-owned scenario engine/report certification; four exercise implementations, manifests and FICHEs; bounded smoke predicates and tests. Component documentation is retained with a historical/publication banner. Private raw reports and physical-topology diagram generators are excluded.

The gate is a bounded publication/privacy regression check, not full SAST, a dependency vulnerability audit, Kubernetes schema/admission validation or a reproducible image build. Owner privacy/provenance review remains required. No public project license is selected.
