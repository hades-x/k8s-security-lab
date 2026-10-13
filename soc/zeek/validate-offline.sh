#!/usr/bin/env bash

# Public candidate: runtime requires separately provisioned disposable lab.
if [[ ${LAB_ALLOW_RUNTIME:-} != yes ]]; then
  printf "%s\n" "BLOCKED: set LAB_ALLOW_RUNTIME=yes only after tools/DEPENDENCIES.md review" >&2
  return 2 2>/dev/null || exit 2
fi
set -euo pipefail
ROOT=$(cd "$(dirname "${BASH_SOURCE[0]}")/../.." && pwd)
export KUBECONFIG=${KUBECONFIG:-/data/k8s-lab/.secrets/kubeconfig}
export PATH="$ROOT/bin:$PATH"
cd "$ROOT"
set -o pipefail
bash soc/detection/validate.sh
helm template falco evidence/p4-prep-b/falco-9.2.0.tgz -n falco -f soc/falco/values.yaml --skip-tests >evidence/p4-prep-b/falco-rendered.yaml
helm template falcosidekick evidence/p4-prep-b/falcosidekick-0.14.0.tgz -n falco -f soc/falco/sidekick-values.yaml --skip-tests >evidence/p4-prep-b/sidekick-rendered.yaml
.venv-traffic/bin/python evidence/p4-prep-b/validate-p4b.py | tee evidence/p4-prep-b/offline-validation.txt
kubeconform -strict -summary -ignore-missing-schemas soc/zeek/manifests.yaml soc/traffic/manifests.yaml soc/traffic/replay-cronjob.yaml soc/traffic/scan-job.json soc/misp/manifests.yaml soc/misp/intel-cronjob.yaml soc/falco/namespace.yaml soc/falco/kafka-acceptance-pod.yaml evidence/p4-prep-b/falco-rendered.yaml evidence/p4-prep-b/sidekick-rendered.yaml | tee evidence/p4-prep-b/kubeconform.txt
