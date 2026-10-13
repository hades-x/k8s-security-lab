#!/usr/bin/env bash

# Public candidate: runtime requires separately provisioned disposable lab.
if [[ ${LAB_ALLOW_RUNTIME:-} != yes ]]; then
  printf "%s\n" "BLOCKED: set LAB_ALLOW_RUNTIME=yes only after tools/DEPENDENCIES.md review" >&2
  return 2 2>/dev/null || exit 2
fi
set -euo pipefail
ROOT=$(cd -- "$(dirname -- "${BASH_SOURCE[0]}")/../.." && pwd)
export PATH="$ROOT/bin:$PATH"
export KUBECONFIG="${KUBECONFIG:-$ROOT/.secrets/kubeconfig}"
export LC_ALL=C
 : "${SIGNED_IMAGE:?Set a digest-pinned prod image signed by the lab key}"
: "${UNSIGNED_IMAGE:?Set a different unsigned digest-pinned lab image}"
[[ $SIGNED_IMAGE == *@sha256:* && $UNSIGNED_IMAGE == *@sha256:* ]]
python3 - "$ROOT" "$SIGNED_IMAGE" "$UNSIGNED_IMAGE" <<'PY'
import sys,yaml,pathlib,subprocess
root=pathlib.Path(sys.argv[1]);template=yaml.safe_load((root/'hardening/kyverno/tests/resources.yaml').read_text().split('---')[0])
for label,image in [('signed',sys.argv[2]),('unsigned',sys.argv[3])]:
 p=template.copy();p['metadata']={'name':'signature-'+label,'namespace':'prod'};p['spec']['containers'][0]['image']=image
 result=subprocess.run(['kubectl','create','--dry-run=server','-f','-'],input=yaml.safe_dump(p),text=True,capture_output=True)
 if label=='signed':assert result.returncode==0,result.stderr
 else:assert result.returncode!=0 and ('verify-lab-signature' in result.stderr or 'lab-prod-signatures' in result.stderr),result.stderr
 print(label, 'PASS')
PY
