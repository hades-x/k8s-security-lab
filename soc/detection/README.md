> Publication candidate: adapted from the October 13, 2026 lab snapshot. Historical PASS statements below are not current health or fresh-clone reproduction. Raw evidence, caches and original trust roots are not distributed. See `tools/DEPENDENCIES.md` from the repository root.

# Lab detection pack

The historical base pack contained 17 original experimental Sigma rules with deterministic unique UUIDs. This candidate contains 18 rule YAML files after the scenario-specific forbidden-Secret addition; it is **not** an 18-rule native deployment. The native installer is unconditionally disabled pending a validated catalogue and missing monitor input adaptation; Alerting preparation and pure rule/query definitions remain available for separately reviewed operator provisioning.
Run `bash soc/detection/validate.sh` (pySigma + OpenSearch backend in `.venv-sigma`).
`lucene/` contains actual backend conversion outputs. No ECS pipeline is appropriate: JSON fields are already named as the rules require. Scalar Zeek `id` must be renamed `zeek_id` by the indexer, not a nested `id.*` object.

| ID | Title | ATT&CK | Log source | Index | Trigger | Expected result |
|---|---|---|---|---|---|---|
| `1f014ba6-f820-589c-9b69-1f26a659f030` | DNS Query To Synthetic Command And Control Domain | T1071.004 | zeek/dns | `zeek-dns-*` | `triggers/dns-c2.sh` | Matching document; disabled fallback monitor sees hits |
| `bc43ff37-5cc3-58d9-9777-8a4aee0b20aa` | Long DNS Labels Consistent With Tunneling | T1572 | zeek/dns | `zeek-dns-*` | `triggers/dns-tunnel.sh` | Matching document; disabled fallback monitor sees hits |
| `b48d22c0-af46-590a-93b8-4c7295b9a54b` | High Entropy DNS Notice | T1568.002 | zeek/notice | `zeek-notice-*` | `triggers/dns-entropy.sh` | Matching document; disabled fallback monitor sees hits |
| `8c9963b2-f768-511e-9964-66bbab3809ae` | Long DNS Query Notice | T1048.003 | zeek/notice | `zeek-notice-*` | `triggers/dns-exfil.sh` | Matching document; disabled fallback monitor sees hits |
| `47ca0771-3620-5def-a70f-381a1484d676` | Synthetic HTTP Beacon User Agent | T1071.001 | zeek/http | `zeek-http-*` | `triggers/http-beacon.sh` | Matching document; disabled fallback monitor sees hits |
| `1f650655-4d3a-5350-a609-a425f0f89ff1` | Synthetic Scan Connection Candidate | T1046 | zeek/conn | `zeek-conn-*` | `triggers/conn-scan.sh` | Matching document; disabled fallback monitor sees hits |
| `b3d2c60a-8459-55c7-9064-96e479245734` | Multiple Destination Ports Within One Minute | T1046 | zeek/notice | `zeek-notice-*` | `triggers/notice-scan.sh` | Matching document; disabled fallback monitor sees hits |
| `96b8005d-26d3-514c-8a7c-bc0bcd025288` | MISP Synthetic Indicator Seen By Zeek | T1071.004 | zeek/intel | `zeek-intel-*` | `triggers/intel-hit.sh` | Matching document; disabled fallback monitor sees hits |
| `4080aaab-6c84-55eb-bb6b-6ad231c6447c` | Kubernetes Pod Deployment In Detection Lab | T1610 | kubernetes/audit | `audit-k8s-*` | `triggers/audit-deploy.sh` | Matching document; disabled fallback monitor sees hits |
| `02d849bb-cc43-5db2-9a4b-650d9b2793dd` | Kubernetes Container Administrative Exec | T1609 | kubernetes/audit | `audit-k8s-*` | `triggers/audit-exec.sh` | Matching document; disabled fallback monitor sees hits |
| `db6080d9-2c31-5274-adf6-f2d24e894f0b` | Kubernetes Secret Read In Detection Lab | T1552.007 | kubernetes/audit | `audit-k8s-*` | `triggers/audit-secrets.sh` | Matching document; disabled fallback monitor sees hits |
| `cca5684e-6e30-5fcb-bacb-5b19fb77ffec` | Anonymous Kubernetes API Access Attempt | T1078 | kubernetes/audit | `audit-k8s-*` | `triggers/audit-anonymous.sh` | Matching document; disabled fallback monitor sees hits |
| `6af9f34c-e49e-5e53-9e87-022c6bc4e03a` | Cluster Role Binding Creation In Lab | T1098 | kubernetes/audit | `audit-k8s-*` | `triggers/audit-rbac.sh` | Matching document; disabled fallback monitor sees hits |
| `4c51fd33-3a75-5859-92c1-74f4d5b70fd0` | Shell Executed In A Container | T1609 | falco/syscall | `falco-alerts-*` | `triggers/falco-shell.sh` | Matching document; disabled fallback monitor sees hits |
| `a61483b8-2bdc-5453-be32-0bd5fa6c3751` | Unexpected Process Reads Service Account Token | T1552.007 | falco/syscall | `falco-alerts-*` | `triggers/falco-token.sh` | Matching document; disabled fallback monitor sees hits |
| `f120ab58-0130-5e7f-baa6-10c9721c4284` | Container Mount Attempt | T1611 | falco/syscall | `falco-alerts-*` | `triggers/falco-mount.sh` | Matching document; disabled fallback monitor sees hits |
| `3ff40d46-3063-5e4b-b9e4-a7a494516de9` | Container Connects To Synthetic C2 Node | T1071.001 | falco/syscall | `falco-alerts-*` | `triggers/falco-c2.sh` | Matching document; disabled fallback monitor sees hits |

## Safe triggers
Set `LAB_TRIGGER=1`. Every trigger validates the configured API server is a lab address before making changes. Network rules replay crafted traffic into the isolated veth, not a routed NIC. API triggers use `soc-detection`; the RBAC trigger briefly creates cluster-admin binding to a unique inert group with no users, then deletes it. It never grants privilege to an existing identity. Mount attempt is an unprivileged tmpfs syscall expected to fail; no host files are mounted or modified. Token read goes to `/dev/null`; no token is printed.
Anonymous access is an attempt and must return 401/403. If Kubernetes rejects unauthenticated requests before auditing, this trigger will not produce an audit event; document that absence rather than weakening API auth.

## Alerting fallback
`queries/<rule>.json` is the search body for an Alerting search input. `monitors/<rule>.json` is a complete disabled monitor, with the exact index selector, a five-minute time window, and an empty actions array (no external notification). `install.sh` explicitly requires HTTPS URL, CA, and netrc and updates named monitors idempotently with GET readback. Security Analytics custom log sources may not accept these fields; these monitors do not depend on that import path. No deployment or OpenSearch hit test has been run in preparation.

Lucene regexp matching is implicitly anchored: do not use `^`/`$` as regex anchors. Long-label regex includes `.*` where substring matching is intended. Keyword field mappings are required for wildcard/regexp/terms/cardinality. False positives include CDN labels and normal administration. Audit rules intentionally detect attempts, not successful exploitation; Metadata-level policy cannot prove the roleRef payload of a binding.

`conn-scan` fallback aggregates distinct destination ports >=12 per source/target; Sigma conversion is only a candidate connection filter. Its alert trigger checks retained source buckets after the bucket selector. `http-beacon-aggregation.json` counts at least six UA hits per source. Count does not establish periodicity or maliciousness; proving beacon regularity requires inter-arrival analysis and a baseline. The handcrafted Zeek scan notice is the simple bounded-window scan detector.
