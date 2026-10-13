#!/usr/bin/env bash

# Public candidate: runtime requires separately provisioned disposable lab.
if [[ ${LAB_ALLOW_RUNTIME:-} != yes ]]; then
  printf "%s\n" "BLOCKED: set LAB_ALLOW_RUNTIME=yes only after tools/DEPENDENCIES.md review" >&2
  return 2 2>/dev/null || exit 2
fi
set -euo pipefail
[[ "${BASH_SOURCE[0]}" != "$0" && "${LAB_TRIGGER:-}" == 1 && -n "${ROOT:-}" ]] || { printf 'Source only from guarded lab triggers\n' >&2; exit 2; }
phase=$(kubectl -n soc-detection get pod lab-trigger -o jsonpath='{.status.phase}' 2>/dev/null || true)
if [[ "$phase" == Succeeded || "$phase" == Failed ]]; then
 kubectl -n soc-detection delete pod lab-trigger --wait=true >/dev/null
fi
kubectl -n soc-detection get pod lab-trigger >/dev/null 2>&1 || kubectl -n soc-detection run lab-trigger --image=docker.io/library/alpine:3.22.2@sha256:4b7ce07002c69e8f3d704a9c5d6fd3053be500b7f1c69fc0d80990c2ad8dd412 --restart=Never --labels=app=lab-trigger --overrides='{"spec":{"containers":[{"name":"lab-trigger","image":"docker.io/library/alpine:3.22.2@sha256:4b7ce07002c69e8f3d704a9c5d6fd3053be500b7f1c69fc0d80990c2ad8dd412","command":["sh","-ec","sleep 3600"],"resources":{"requests":{"cpu":"10m","memory":"16Mi"},"limits":{"cpu":"100m","memory":"64Mi"}},"securityContext":{"allowPrivilegeEscalation":false,"capabilities":{"drop":["ALL"]}}}]}}'
kubectl -n soc-detection wait --for=condition=Ready pod/lab-trigger --timeout=120s
