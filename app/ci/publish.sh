#!/bin/sh

# Public candidate: runtime requires separately provisioned disposable lab.
if [[ ${LAB_ALLOW_RUNTIME:-} != yes ]]; then
  printf "%s\n" "BLOCKED: set LAB_ALLOW_RUNTIME=yes only after tools/DEPENDENCIES.md review" >&2
  return 2 2>/dev/null || exit 2
fi
set -eu
apk add --no-cache python3 py3-yaml ca-certificates >/dev/null
python3 - <<'PY'
import os,pathlib,base64,json
p=pathlib.Path('.ci-auth');p.mkdir(exist_ok=True);p.chmod(0o700)
(p/'config.json').write_text(json.dumps({'auths':{'zot.192.168.150.200.sslip.io':{'auth':base64.b64encode(('lab:'+os.environ['ZOT_PASSWORD']).encode()).decode()}}}))
(p/'cosign.key').write_text(os.environ['COSIGN_KEY']);(p/'cosign.key').chmod(0o600)
pathlib.Path('/usr/local/share/ca-certificates/lab.crt').write_text(os.environ['LAB_CA'])
PY
trap 'rm -rf .ci-auth' EXIT
update-ca-certificates >/dev/null
python3 ci/tools.py
export DOCKER_CONFIG="$PWD/.ci-auth"
ref="zot.192.168.150.200.sslip.io/lab/demo-app:$CI_COMMIT_SHA"
.ci-bin/crane push image-oci "$ref"
digest=$(.ci-bin/crane digest "$ref")
test "$digest" = "$(tr -d '\n' < image.digest)"
ref="zot.192.168.150.200.sslip.io/lab/demo-app@$digest"
.ci-bin/cosign sign --yes --key .ci-auth/cosign.key --tlog-upload=false --use-signing-config=false --new-bundle-format=false --registry-referrers-mode=legacy "$ref"
.ci-bin/cosign verify --key ci/cosign.pub --insecure-ignore-tlog=true "$ref" >/dev/null
export IMAGE_DIGEST="$digest"
python3 ci/update-gitops.py
printf 'PASS pushed scanned signed verified image %s\n' "$ref"
