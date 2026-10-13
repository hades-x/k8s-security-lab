#!/usr/bin/env bash

# Public candidate: runtime requires separately provisioned disposable lab.
if [[ ${LAB_ALLOW_RUNTIME:-} != yes ]]; then
  printf "%s\n" "BLOCKED: set LAB_ALLOW_RUNTIME=yes only after tools/DEPENDENCIES.md review" >&2
  return 2 2>/dev/null || exit 2
fi
source /data/k8s-lab/infra-services/common.sh
require_lab
kubectl wait clusterissuer/lab-acme --for=condition=Ready --timeout=300s
kubectl -n pki wait certificate/acme-test --for=condition=Ready --timeout=600s
[[ $(kubectl -n pki get certificate acme-test -o jsonpath='{.spec.issuerRef.name}') == lab-acme ]]
echo 'PASS: acme-test Ready=True; issuerRef=lab-acme (step-ca ACME)'
