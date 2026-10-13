> Publication candidate: adapted from the October 13, 2026 lab snapshot. Historical PASS statements below are not current health or fresh-clone reproduction. Raw evidence, caches and original trust roots are not distributed. See `tools/DEPENDENCIES.md` from the repository root.

# Simulated offline PKI

This is an isolated throwaway CA, NOT the real homelab PKI. `step` generated a new
root and signed a new intermediate locally. The encrypted root key and password
were **put aside** in `.secrets/pki/offline/`; neither is mounted in Kubernetes.
This simulates offline-root operational discipline, not physical offline storage:
the host still holds the key. In this candidate the original public certificates are **removed** and their configuration values are regeneration placeholders; generate a new root/intermediate before deployment. Private keys/passwords must remain mode 600 under `.secrets/pki/`.

`step-certificates` uses existing Secrets containing only the encrypted intermediate
and its password. Its bootstrap Job is disabled. `lab-acme` uses the internal HTTPS
ACME directory and an explicit root caBundle (no insecureSkipVerify).
HTTP-01 uses Traefik; step-ca and cert-manager must resolve/reach sslip names at
192.168.150.200 through the lab VIP. External DNS rebinding protection or broken
VIP hairpin routing can block issuance. `acme-test` proves ACME, not fallback.
`lab-ca` is an explicit fallback using a decrypted copy of the intermediate key in
cert-manager's cluster-resource namespace. It expands key exposure; remove it if
unneeded. It is never substituted silently for ACME.

Gateway API standard CRDs are vendored and support is enabled in cert-manager's
ControllerConfiguration. HTTP-01 deliberately remains Ingress-based.
Distribute ONLY `root_ca.crt` to browser/OS/Java trust stores, or copy it into app
ConfigMaps via the integrator. Do not globally disable certificate verification.
Grafana mounts the root bundle for OIDC; Forgejo and Argo CD now trust the same
public root. OpenSearch snippets remain prepared but unapplied.
Trust-manager is optional and not installed to save resources.

Install: `P3_ALLOW_DEPLOY=yes ./infra-services/pki/install.sh`
Verify: `P3_ALLOW_DEPLOY=yes ./infra-services/pki/test.sh`

Gateway API version is resolved from the upstream releases/latest redirect; GitHub
API rate limiting was avoided by downloading the exact release asset.

The chart-default cr.smallstep.com image registry returned HTTP 429 during digest
lookup. The official smallstep/step-ca Docker Hub mirror is pinned by digest;
upstream certificates/releases/latest confirmed stable v0.30.2.

Live proof: `python3 chain-check.py` compares the served Grafana leaf with
cert-manager Secret `grafana-tls`, verifies its hostname and root/intermediate chain
with OpenSSL, and runs `curl --cacert` against `/api/health`. Both `acme-test` and
Grafana use `lab-acme`, not fallback. Evidence: `evidence/p3/17-tls-chain.txt`,
`tls-chain-test.txt`, and `21-offline-root-isolation.txt`. The root certificate is
public; the encrypted offline root key/password are never mounted.
