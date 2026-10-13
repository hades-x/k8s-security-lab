> Publication candidate: adapted from the October 13, 2026 lab snapshot. Historical PASS statements below are not current health or fresh-clone reproduction. Raw evidence, caches and original trust roots are not distributed. See `tools/DEPENDENCIES.md` from the repository root.

# zot OCI registry

Official zot image pinned to a stable release; one 10Gi local-path PVC. HTTPS
Ingress: zot.192.168.150.200.sslip.io; Certificate issued through lab-acme.
Authentication is bcrypt htpasswd for user `lab`, generated with random password
in `.secrets/p3/zot-password` and `.secrets/p3/zot.htpasswd`, both mode 600.
No image was pushed during preparation. Live `test.sh` validates trusted TLS,
401 without credentials, 200 on authenticated /v2/, and a real authenticated
OCI scratch image push/pull/export roundtrip. `install-crane.py` downloads pinned
crane v0.22.1 into lab-local `bin/`, verifies official archive and binary SHA-256,
and refuses an unexpected existing binary. Credentials/configs and tar artifacts
remain in `.secrets/p3/registry-proof/` (never printed). The test pushes only to
`zot.192.168.150.200.sslip.io/lab/p3-proof:v1`; exported file checksum equals the
input checksum. Evidence: `evidence/p3/12-crane-download.txt` and
`13-registry-push-pull.txt`. Node/containerd pull trust remains a P6 exercise;
no k3s node was restarted for P3. Network policy, vulnerability scanning and HA are not provided.

P6: merge registries.yaml.example into /etc/rancher/k3s/registries.yaml **inside
lab VMs only**, copy ONLY the lab public root to the configured ca_file, populate
password from the local secret file without logging it, and restart k3s/k3s-agent
in a controlled window. No insecure_skip_verify. Never mirror docker.io wholesale:
only images explicitly named with this zot hostname use this endpoint. Root path
is an example usable on all nodes; do not assume /server exists on agents: create
the lab certificate parent directory or choose another shared node-local path.
Alternatively create a namespaced kubernetes.io/dockerconfigjson imagePullSecret
from the local credentials; containerd still needs the lab CA trust.
