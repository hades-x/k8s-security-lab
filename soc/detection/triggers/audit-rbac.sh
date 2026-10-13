#!/usr/bin/env bash

# Public candidate: runtime requires separately provisioned disposable lab.
if [[ ${LAB_ALLOW_RUNTIME:-} != yes ]]; then
  printf "%s\n" "BLOCKED: set LAB_ALLOW_RUNTIME=yes only after tools/DEPENDENCIES.md review" >&2
  return 2 2>/dev/null || exit 2
fi
set -euo pipefail
source "$(dirname "${BASH_SOURCE[0]}")/_common.sh"
# The group does not represent any real subject and is removed immediately.
trap 'kubectl delete clusterrolebinding lab-inert-admin-binding --ignore-not-found >/dev/null' EXIT
kubectl delete clusterrolebinding lab-inert-admin-binding --ignore-not-found >/dev/null
kubectl create clusterrolebinding lab-inert-admin-binding --clusterrole=cluster-admin --group=k8s-lab-inert-no-members-7c3580a8

