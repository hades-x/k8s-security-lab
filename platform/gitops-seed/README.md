> Publication candidate: adapted from the October 13, 2026 lab snapshot. Historical PASS statements below are not current health or fresh-clone reproduction. Raw evidence, caches and original trust roots are not distributed. See `tools/DEPENDENCIES.md` from the repository root.

Source of truth copied to local Forgejo lab/gitops.
App: digest-pinned unprivileged nginx, Service, Ingress and Longhorn PVC.
Argo CD automatically syncs/self-heals these manifests.
Demo: http://demo.192.168.150.200.sslip.io/.
Run `../forgejo/seed.py` after edits to update the local Forgejo copy.
