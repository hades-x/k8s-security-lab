> Publication candidate: adapted from the October 13, 2026 lab snapshot. Historical PASS statements below are not current health or fresh-clone reproduction. Raw evidence, caches and original trust roots are not distributed. See `tools/DEPENDENCIES.md` from the repository root.

# Lab identity

Maintained `vegardit/openldap` (OpenLDAP 2.6.10, weekly OS rebuilds) is pinned by
immutable multi-architecture digest. It avoids paywalled Bitnami images and the
old osixia image. Base DN: `dc=k8slab,dc=lab`; users: `lab-admin`, `lab-analyst`,
`lab-dev`; groups: `lab-admins`, `soc-analysts`, `devs`. Password files and salted
bootstrap LDIF live only in `.secrets/p3/`. SSHA bootstrap hashing is a lab-only
compatibility compromise; use Argon2 for later password changes.
LDAP is cluster-internal plaintext: no internet ingress, but network policy and
LDAPS hardening are integrator follow-up work.

Keycloak uses the official Quay image and a persistent embedded `dev-file` DB,
one replica with Recreate strategy. This deliberately saves PostgreSQL/CNPG RAM
and is NOT production/HA. `start-dev` is explicit; HTTPS terminates at Traefik.
Do not expose this lab beyond its network. Realm import contains environment
placeholders only, substituted from Kubernetes Secrets at startup. Import only
creates a missing realm: reruns do NOT update an existing realm or rotate secrets.
Use Keycloak admin API/UI to reconcile later changes (no destructive realm reset).
LDAP user federation is read-only; the group mapper emits short group names in
OIDC tokens. The `lab-cli` public direct-grant client is lab-test-only; disable it
when finished. All real application clients use authorization code + PKCE.

Grafana OAuth values are in `../observability/prometheus-values.yaml` and activated
by its installer. Argo CD snippets must be **merged** with P2 config, not replace
whole ConfigMaps. Store the argocd secret key `oidc.keycloak.clientSecret` in
argocd-secret (from `.secrets/p3/argocd-client-secret`) and mount/merge root trust;
`lab-admins` maps to role:admin. Forgejo CLI: `forgejo-source.sh`, run as its service
user with the correct existing config path if P2's image requires it; mount root CA
into its trust store before discovery. OpenSearch snippets are merge fragments,
not a complete security config: retain internal/break-glass auth, map lab-admins to
all_access and soc-analysts to read roles in roles_mapping.yml; mount root_ca.crt
and inject the Dashboards client secret through its Secret environment. Service
hostname contracts are listed in realm JSON; ensure P4 matches them.

`test.sh` validates discovery and password-token issuance for all three LDAP users
plus group claims. Completed application SSO is verified separately by
`sso-session-check.py grafana|argocd|forgejo`; phase-p3 runs all three. Real LDAP
form POST -> Keycloak code redirect -> app callback -> app session was exercised:
Grafana `/api/user` returns `lab-analyst`; Argo CD `/api/v1/session/userinfo` returns
`lab-analyst@k8slab.lab` and `soc-analysts`; Forgejo authenticated settings/account
pages identify that LDAP user/email. Forgejo's browser session is not a `/api/v1/user`
API credential (that API rejects the cookie with 401), so no Forgejo API-auth claim.
Argo CD OIDC enables PKCE and trusts the lab root. Forgejo mounts the lab root in
its container CA directory, uses HTTPS ROOT_URL, and enables OAuth-only automatic
account provisioning while keeping local registration disabled and explicit account
linking for existing users. `install-app-oidc.sh` installs these narrow P2 values
and injects the Argo secret/source idempotently. P2 regression tests pass afterwards.
Do not apply the OpenSearch snippets automatically; they remain a separate handoff.

LDAP daily export is disabled with LDAP_BACKUP_TIME empty. The image still makes
an initial export inside its own persistent PVC; no host/homelab backup path.
