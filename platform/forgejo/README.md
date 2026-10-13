> Publication candidate: adapted from the October 13, 2026 lab snapshot. Historical PASS statements below are not current health or fresh-clone reproduction. Raw evidence, caches and original trust roots are not distributed. See `tools/DEPENDENCIES.md` from the repository root.

Forgejo 15.0.9 via OCI chart 17.2.0, SQLite and one replica.
2Gi Longhorn PVC; signup disabled.
Run `./install.sh`; generated admin password stays in `.secrets`.
`seed.py` creates/verifies local lab/gitops using the Forgejo API.
No git push or public/cloud publication is performed.
Verify `./test.sh`.
