> Publication candidate: adapted from the October 13, 2026 lab snapshot. Historical PASS statements below are not current health or fresh-clone reproduction. Raw evidence, caches and original trust roots are not distributed. See `tools/DEPENDENCIES.md` from the repository root.

# Budget observability

Pinned kube-prometheus-stack; Prometheus 2d retention, 8GB retention size on 10Gi
local-path PVC, Grafana persistent with dashboard sidecar. Control-plane etcd,
scheduler, controller-manager and kube-proxy scrapes are disabled because k3s
bundles these and Cilium replaces kube-proxy; no fake targets. Loki is single-binary
with filesystem PVC, replication 1, 48h retention, no caches/gateway/canary.
Alloy is a DaemonSet filtering discovery to its own node; API-based pod log tails
avoid privileged hostPath mounts and duplicated all-cluster log ingestion.

Grafana generic_oauth + PKCE is preconfigured; client secret injected from local
Secret file, root CA mounted for validated Keycloak HTTPS. `test.sh` proves LDAP
password token/group claims, discovery, Grafana's OAuth redirect/client/PKCE,
all configured Prometheus targets up, the three lab dashboards, real Loki lines,
loaded rules, and a firing test alert in Alertmanager. The phase test additionally
runs `../identity/sso-session-check.py grafana`: a real HTML authorization-code
login with the LDAP user `lab-analyst`, followed by authenticated `/api/user`.
An ID/access token is NOT treated as a Grafana API bearer credential. The test uses
the Grafana session returned after code exchange; no cookie/token/password is logged.
Admin-vs-Viewer RBAC is configured but not separately exercised by this acceptance.

Three sidecar dashboard ConfigMaps: cluster, Kafka exporter and Cilium/Hubble.
Kafka and Cilium/Hubble dashboards legitimately show no data until P4/P6 enables
those metrics + ServiceMonitors. Kafka lag alert is conditional on exporter
metrics being present, not absent(). To expose k3s node metrics Cilium policies
must allow monitoring -> kubelet. Certificate expiry uses cert-manager metrics;
additional ServiceMonitor is installed. Falco integration is deferred/optional.

Checks fail if *any* configured Prometheus target is down, and require real Loki
pod-log query results. Alerts cover node Ready, CrashLoopBackOff, Kafka lag, PVC
free ratio <10%, certificate remaining <12h. `LabP3AcceptanceAlwaysFiring` deliberately uses `vector(1)` and severity `warning`,
so the chart-default InfoInhibitor does not suppress it. It remains installed for
training; remove that one rule after the exercise if desired. No external notification
channel is configured; delivery to Alertmanager's active alert list is proven. Volumes are single-node local-path, not replicated production storage.

## Live memory and k3s metrics

Initial prepared limits caused real OOMs: Grafana/sidecars, then Prometheus.
Current caps are Grafana 384Mi, two sidecars 128Mi each, Prometheus 1024Mi,
Loki 256Mi. P3 steady limits total 6088Mi (5.95Gi), including the retained drill.
K3s multiplexes control-plane metrics on kubelet `/metrics`; before filtering
the Prometheus head contained 452216 series, including duplicated API/etcd/scheduler
histograms. Kubelet `/metrics` now keeps kubelet/storage/CSI/rest-client/process/Go
metrics; the API job keeps API/process/Go metrics. Chart histogram filters remain;
cAdvisor and pod-probe endpoints are unaffected. Old TSDB head series retire through
normal compaction; no monitoring data was deleted. This is a small training profile,
not full control-plane SLO coverage. Watch memory as workload/cardinality grows.
