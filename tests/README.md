# Local verification and live lab smoke

## Offline default

`make test`, `make check` and `make ci` are aliases for the publication candidate's **offline** gate. They run reviewed stdlib unittest suites, Python AST/Bash syntax/JSON parsing and the public artifact/privacy/link audit. They do not contact Kubernetes, start containers, download tools, change HOME, create lab evidence or discover arbitrary `test.sh` scripts.

Use `make test-offline` for only the seven unit suites; `make syntax` for parsing only; `make audit` for the all-candidate-file scan. See [operator prerequisites](../tools/DEPENDENCIES.md).

## Retained live smoke

On an independently provisioned disposable lab controller at `/data/k8s-lab`, after source/prerequisite review:

```sh
# Explicit consent: this is NOT an offline command.
LAB_ALLOW_RUNTIME=yes make smoke
```

This invokes `tests/smoke-test.sh` and its bounded stdlib helper. It uses Kubernetes/HTTP GETs and existing guest SSH commands, and temporarily opens loopback port-forward tunnels. It is intended to avoid cluster resource writes, not to avoid all local files/tunnels. The runtime environment helper redirects HOME/caches to the lab directory only after the authorization guard.

Four workers, per-check deadlines and a 150-second total budget prevent indefinite waits. Missing, stale, unhealthy or timed-out resources fail; a passing controller count is not a quorum/restore guarantee. The returned script status is the FAIL-row count (Make may return its own failure code).

Monitor checks require a **fresh operator-generated** `evidence/p4/alerting-state.json`. The candidate excludes historical monitor IDs and fails with an explicit prerequisite when that registry is missing; run the reviewed Alerting installer during independent provisioning, not during offline CI. Original credentials, trust roots, private images and evidence are not supplied.

The `phase-*.sh` files are full live acceptance suites: they may create/delete workloads, pause consumers, produce synthetic data, push to an in-lab forge or reboot guests. They are runtime-gated and are never called by the offline Make targets. Their mere presence is not a fresh-clone PASS. No live phase suite was executed to prepare this candidate.
