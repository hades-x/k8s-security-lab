> Publication candidate: adapted from the October 13, 2026 lab snapshot. Historical PASS statements below are not current health or fresh-clone reproduction. Raw evidence, caches and original trust roots are not distributed. See `tools/DEPENDENCIES.md` from the repository root.

# Throwaway OpenBao + External Secrets

This is a NEW disposable instance in namespace `secrets`. It is distinct from the
real lab OpenBao. Never copy PKI, tokens, unseal material or endpoints from the real
homelab. Official OpenBao Helm chart; single-node persistent Raft storage, **not
`-dev`**. One-share/one-threshold Shamir init is deliberately lab-only. Install
starts sealed without Helm --wait, writes validated init JSON atomically into
`/data/k8s-lab/.secrets/p3/openbao-init.json` (600), then unseals and configures
KV v2 and Kubernetes auth. No keys/tokens are printed. Rerun `unseal.sh` after
server restart; automatic unseal is not configured. Backup of PVCs alone does not
recover this server without its init keys; keep the init file separately.

ESO uses a namespaced SA and audience `openbao`, bound only to `eso-demo` with read
access to `kv/data/demo`. OpenBao's pod SA has system:auth-delegator through the
chart. Kubernetes auth uses the pod's local rotating reviewer token. Root token
is used only for bootstrap on this host, never mounted in ESO.

HTTP is confined to the cluster, with no Ingress. No production security claim:
TLS/mTLS, network policies, multi-share quorum, audit storage and auto-unseal are
future exercises. Demonstration plaintext is intentionally public, not a real
secret. `test.sh` checks Store and ExternalSecret Ready, exact synced demonstration content,
KV v2/Kubernetes-auth enablement, unsealed status, and matching source/target key names.
All credential and Secret values are withheld. OpenBao 2.7.1 no longer accepts
`storage "file"`; the live installer therefore uses a one-node Raft backend.
Evidence: `evidence/p3/20-secrets-readback.txt` and `secrets-test.txt`.
