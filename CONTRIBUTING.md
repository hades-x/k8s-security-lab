# Contributing and local verification

No project license is currently selected. Public visibility is not an open-source license grant. Do not add a license or claim redistribution rights without the owner's explicit decision; preserve upstream attribution for any authorized third-party additions.

1. Read [security scope](SECURITY.md) and [operator prerequisites](tools/DEPENDENCIES.md).
2. Work on an isolated local copy; do not run deployment or acceptance scripts on somebody else's infrastructure.
3. Add a regression test for a changed behavior, then run `make ci`. This runs the same offline command used by GitHub Actions, with no downloads or cluster access.
4. Review all generated manifests, encoded fields, symlinks and candidate files for privacy. Keep evidence, credentials, caches and original infrastructure inventory out of publication.
5. Update component documentation and explicitly distinguish expected outcomes, historical observations and new verified results. Preserve known failures and non-reproduction boundaries.

The official `actions/checkout` v4.4.0 tag was resolved from its upstream repository to `11d5960a326750d5838078e36cf38b85af677262`. The workflow is commit-pinned, contents-read-only, credential persistence disabled, and timeout-bounded. Action upgrades require deliberate official tag-to-commit verification. Ubuntu runner and system Python are not immutable OS artifacts; hosted execution and fresh-clone cluster recreation remain separate verification tasks.

No live test, remote push, CI publication, dependency installation or infrastructure mutation is required for a documentation/code contribution's local gate. A maintainer must explicitly approve those separate actions.
