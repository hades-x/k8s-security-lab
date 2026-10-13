# Third-party provenance and redistribution boundary

**No public project license is selected.** This file records provenance boundaries; it does not grant a license or assert that the whole repository is licensed open source. Dependencies referenced by manifests retain their upstream terms. Version/digest records are historical pins, not claims of current upstream releases or present availability.

## Excluded bundled material

- The original upstream k3s installer (`infra/k3s/install-k3s.sh`) is not redistributed. Its checksum and release pin remain for an operator-controlled official fetch.
- Gateway API standard CRD bundles from `kubernetes-sigs/gateway-api` (two old bundle paths) are excluded. Version v1.6.3 and SHA-256 remain in the respective version/checksum files. Fetch and review upstream licensing separately before bundling them.
- `devsecops/vendor` (upstream chart values, API schema, Go source and Woodpecker documentation), Kubescape framework caches, Helm archives, binaries, CRD-schema caches, vendorized agent skills and prior Git history are excluded.
- The physical-topology diagram generator and original skill-derived design artifacts are excluded; public documentation uses authored Mermaid diagrams instead. The private SKILLS.lock is not a public dependency or a redistribution approval.

## Referenced dependencies, not bundled distributions

Component `VERSIONS` files and image references identify the K3s/Kubernetes ecosystem, Cilium, Traefik, Longhorn, Forgejo, Argo CD, Smallstep/cert-manager, OpenBao/External Secrets, Keycloak/OpenLDAP, Prometheus/Grafana/Loki/Alloy, Velero/Garage, zot, Strimzi/Kafka, OpenSearch, Vector, Zeek, MISP, Falco/Falcosidekick, Kyverno/Trivy/Kubescape/kube-bench, Woodpecker/Kaniko/Cosign, CNPG/PostgreSQL, Valkey and Python application libraries. No container images, Python distributions or upstream chart archives are included in this snapshot; obtain them from their named official registries/projects and review their own licenses/notices before redistribution.

The GitHub workflow references, but does not bundle, `actions/checkout` at immutable commit `11d5960a326750d5838078e36cf38b85af677262` (official v4.4.0 tag verified). No public GitHub CI run is implied by local validation.

## Remaining provenance review

Repository-authored policies, synthetic fixtures, charts, original experimental detection rules are preserved; generated/live dashboard NDJSON exports and upstream field metadata responses are excluded as raw state, while the authored importer is retained. This staging review found no separate upstream license/notice attached to those authored files, but that alone does not establish exclusive authorship or redistribution permission. The owner must confirm provenance of retained configuration adaptations and generated code before publication. If any asset was copied from upstream rather than authored, add its exact source/revision, copyright notice and required license text, or exclude it. Do not invent a blanket license to conceal uncertainty.
