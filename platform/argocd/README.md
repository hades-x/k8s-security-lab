> Publication candidate: adapted from the October 13, 2026 lab snapshot. Historical PASS statements below are not current health or fresh-clone reproduction. Raw evidence, caches and original trust roots are not distributed. See `tools/DEPENDENCIES.md` from the repository root.

Argo CD 3.5.5 via chart 10.10.3, minimal single-replica components.
Dex, notifications and ApplicationSet disabled to save resources.
Run `./install.sh`; admin password is saved only in `.secrets`.
`application.yaml` syncs public in-cluster Forgejo lab/gitops main.
Verify `./test.sh`.
