SHELL := /bin/bash
.DEFAULT_GOAL := help
export LC_ALL := C
export PYTHONDONTWRITEBYTECODE := 1
.PHONY: help check ci test audit test-offline syntax status status-quick smoke start stop creds
help:
	@printf '%s\n' 'make check / ci / test: offline syntax, unit suites and public audit' 'make audit: all-file privacy, secrets, artifact and Markdown-link gate' 'make test-offline: reviewed standard-library suites only' 'make smoke: opt-in live read-only smoke; not portable reproduction' 'Runtime requires LAB_ALLOW_RUNTIME=yes and tools/DEPENDENCIES.md review.'
check ci test:
	@python3 tools/offline_check.py
	@python3 tools/public_audit.py
test-offline:
	@python3 tools/offline_check.py --tests-only
syntax:
	@python3 tools/offline_check.py --syntax-only
audit:
	@python3 tools/public_audit.py
smoke:
	@bash tests/smoke-test.sh
status status-quick:
	@bash scripts/lab-status.sh --quick
start stop creds:
	@printf '%s\n' 'BLOCKED: original private host orchestration is not distributed. Provision and manage your own disposable lab.' >&2; exit 2
