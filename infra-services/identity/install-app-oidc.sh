#!/usr/bin/env bash

# Public candidate: runtime requires separately provisioned disposable lab.
if [[ ${LAB_ALLOW_RUNTIME:-} != yes ]]; then
  printf "%s\n" "BLOCKED: set LAB_ALLOW_RUNTIME=yes only after tools/DEPENDENCIES.md review" >&2
  return 2 2>/dev/null || exit 2
fi
# P2 integrations: only app OIDC trust/configuration; no other P2 resources.
source /data/k8s-lab/infra-services/common.sh
require_lab
python3 - <<'PY'
import pathlib,json,base64,subprocess
r=pathlib.Path('/data/k8s-lab');k=str(r/'bin/kubectl')
payload={'data':{'oidc.keycloak.clientSecret':base64.b64encode((r/'.secrets/p3/argocd-client-secret').read_bytes()).decode()}}
p=subprocess.run([k,'-n','argocd','patch','secret','argocd-secret','--type=merge','--patch-file=/dev/stdin'],input=json.dumps(payload),text=True,capture_output=True)
assert p.returncode==0,'Argo CD OIDC Secret patch failed; output withheld'
print('PASS: Argo CD OIDC Secret injected; values withheld')
PY
kubectl -n forgejo create configmap lab-root --from-file="root_ca.crt=$ROOT/.secrets/pki/root_ca.crt" --dry-run=client -o yaml | kubectl apply -f -
"$ROOT/platform/argocd/install.sh"
kubectl -n argocd rollout restart deployment/argocd-server
kubectl -n argocd rollout status deployment/argocd-server --timeout=180s
"$ROOT/platform/forgejo/install.sh"
"$ROOT/infra-services/identity/forgejo-source.sh"
