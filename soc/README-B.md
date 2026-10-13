> Publication candidate: adapted from the October 13, 2026 lab snapshot. Historical PASS statements below are not current health or fresh-clone reproduction. Raw evidence, caches and original trust roots are not distributed. See `tools/DEPENDENCIES.md` from the repository root.

# Phase P4-B: offline sensor and detection preparation

Nothing in this preparation is deployed. No host Docker/libvirt, networking, packages, or existing VM was changed. Worker-owned paths only, no commits.

## Deployment order (after cluster + part A prerequisites)
```bash
cd /data/k8s-lab
export KUBECONFIG=/data/k8s-lab/.secrets/kubeconfig
# Kafka + Strimzi users/topics and OpenSearch/indexer/Vector are part A.
NODE_INTERFACE=enp1s0 bash soc/zeek/install.sh
bash soc/traffic/install.sh
bash soc/misp/install.sh
bash soc/misp/bootstrap.sh
bash soc/falco/install.sh
LAB_TRIGGER=1 bash tests/phase-p4-b.sh
# Optional explicit alert import: set URL, CA and chmod-600 NETRC, then:
bash soc/detection/install.sh
```
Set `NODE=lab-a2` (default) for replay; NIC is configurable via `NODE_INTERFACE`. VM NIC discovery must be performed before install. Cilium must use NATIVE routing with pod CIDR 10.42.0.0/16, services 10.43.0.0/16, nodes 192.168.150.0/24. Cross-node east-west pod IPs remain visible on the physical NIC.

## Contracts
- Two Zeek processes/node capture the node NIC and isolated veth `zeektap0`. Replays transmit on `zeektap0-in`; no address/route is configured on these links. Explicit veth MACs do not match crafted destination MACs, so the Linux receive path sees OTHERHOST frames and does not forward forged packets into the routed lab network.
- Both sensors write separate JSON streams to bounded shared emptyDir. A single merger publishes `/var/log/zeek/current/<type>.log` hostPath and adds `sensor=live|tap` and `capture_source=live|tap` (capture_source survives part A overriding sensor with the node name), avoiding concurrent filename corruption. Log rotation is hourly upstream and size-based bounded at 32MiB x 4 per published type; checkpoints persist with hostPath. At-least-once after a crash is possible. Vector must tail only `*.log`, follow renamed inodes, and persist offsets; long outages beyond retained history can lose data. Do not index loaded_scripts/reporter/stats/packet_filter logs. Zeek script compilation was not executed (no host Zeek/no Docker).
- Vector -> Kafka `zeek-<type>` -> OpenSearch `zeek-<type>-YYYY.MM.dd`; indexer adds `log_type`, preserves `id.*`, renames scalar `id` to `zeek_id`. Audit -> `audit-k8s`; Falco -> `falco-alerts` -> `falco-alerts-*`. Confirm part A index names and mappings; adjust explicit selectors if its indexer differs.
- MISP synthetic event -> REST exporter -> Zeek intel ConfigMap -> intel.log -> Kafka zeek-intel -> OpenSearch zeek-intel-* -> disabled fallback monitor. URL indicators remove scheme. Header-only intel is valid; notice metadata is explicitly T. CronJob refreshes every five minutes, ConfigMap directory mounts refresh asynchronously and Zeek rereads the file; item expiration 20 minutes limits stale indicators. Bootstrap explicitly restarts Zeek after projection refresh for the first hit test.
- Falcosidekick broker `soc-kafka-bootstrap.kafka.svc:9093`, TLS CA from `soc-cluster-ca-cert`, SASL SCRAM-SHA-512 user `falcosidekick`; Helm syntax is `SCRAM_SHA512` (not broker's hyphenated mechanism). Install copies these two secrets into falco without printing data. Kafka TLS uses Go's system certificate pool and `SSL_CERT_FILE=/kafka-ca/ca.crt`, based on reviewed upstream kafka.go. Password is env-from-secret, not Helm values. Repeat install after password/CA rotation.

## RAM budget (requests / limits)
| Component | Requests | Limits |
|---|---:|---:|
| Zeek 2 sensors + merger per node | 544 MiB | 1152 MiB |
| Zeek all five nodes | 2720 MiB | 5760 MiB |
| Falco per node / all five | 256 / 1280 MiB | 512 / 2560 MiB |
| Falcosidekick | 64 MiB | 128 MiB |
| MISP core + nginx + MariaDB + Valkey | 1120 MiB | 2048 MiB |
| Three live traffic deployments | 96 MiB | 288 MiB |
| Replay / exporter (transient) | 32 / 32 MiB | 128 / 96 MiB |
| Kafka acceptance consumer (transient) | 128 MiB | 384 MiB |
CPU and memory requests/limits are present on every deployed container. Chart `helm test` curl hook is not used and is excluded from rendered validation. No claim is made about measured RAM before deployment.

## Security and risks
PSS exemptions are namespace-scoped privileged labels only on `soc-sensors` (hostNetwork/hostPath/NET_RAW/NET_ADMIN) and `falco` (host mounts + modern eBPF). Zeek itself is not privileged and drops all capabilities except NET_RAW/NET_ADMIN; init only NET_ADMIN, merger none. Falco uses the chart's least-privileged modern eBPF mode, requiring suitable kernel BTF/BPF/PERFMON support. Baseline namespaces contain the unprivileged generators and MISP.

Pinned images include manifest-list digests resolved through registry APIs (no pull). Zeek 9.0.0, MISP 2.5.50 core+separate nginx, MariaDB 11.8.6 (LTS branch), Valkey 9.1.2, Falco 0.45.0, sidekick 2.35.0; exact references in VERSIONS. Supporting Alpine/Python are fixed tested preparation bases, not claims of newest upstream. `apk add` in init/replay/scan requires repository egress on first start with explicitly locked package versions; package-lock evidence records repository index hashes but transitive dependencies and availability still require runtime repositories. Build a derivative image in a VM/CI and pin its digest before treating this as an air-gapped deployment. The generator never sends fake-domain DNS to external resolvers; live DNS is answered by the lab server, which does not forward.

MISP is a lab-only internal HTTP endpoint, also exposed on the lab ingress hostname; use only the isolated lab network and port-forward for bootstrap. Add ingress TLS and a read-only MISP exporter API user before any broader use (initial exporter uses generated lab admin API key). `DISABLE_PRINTING_PLAINTEXT_CREDENTIALS=true` prevents official bootstrap logs revealing the API key/password. Credentials generated idempotently in `.secrets/`, never in tracked manifests. Local-path volumes bind the first scheduled node; backups/rescheduling need explicit work. Modules and email service are omitted; worker counts are reduced to one default and one update worker with PHP memory 256MiB and two FPM children; core initialization needs runtime smoke testing, 5-15 minute startup and tuning may be required within 2GiB. Do not treat API attempt rules as successful attacks.

## Static evidence and deferred acceptance
`evidence/p4-prep-b/` contains registry digests, chart hashes, upstream configurations, 17-rule pySigma validation and conversion, rendered Helm resources, strict kubeconform, offline exporter fixture output, crafted pcap counts, merger tests and shell/Python parsing results. PCAP binaries are gitignored and rebuilt from Scapy script.
Live checks require the actual cluster: exactly 5 Ready Zeek pods with logs, isolated replay dns/conn/http/notice, authenticated MISP event, intel hit after export, Falco modern-eBPF startup, and authenticated fresh Kafka proof event (latest offsets snapshotted before a unique shell marker; manual partition reader never joins the indexer consumer group). No live acceptance, OpenSearch query hit, or Zeek syntax execution is claimed offline.
