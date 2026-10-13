#!/usr/bin/env bash

# Public candidate: runtime requires separately provisioned disposable lab.
if [[ ${LAB_ALLOW_RUNTIME:-} != yes ]]; then
  printf "%s\n" "BLOCKED: set LAB_ALLOW_RUNTIME=yes only after tools/DEPENDENCIES.md review" >&2
  return 2 2>/dev/null || exit 2
fi
set -euo pipefail
export LC_ALL=C
umask 077
python3 - <<'PY'
from pathlib import Path
import secrets,os
p=Path('/data/k8s-lab/.secrets');p.mkdir(mode=0o700,exist_ok=True)
for name in ['admin','dashboards','soc-indexer','soc-analyst']:
 f=p/('opensearch-'+name+'.password')
 if not f.exists():
  fd=os.open(f,os.O_WRONLY|os.O_CREAT|os.O_EXCL,0o600)
  with os.fdopen(fd,'w') as out:out.write('Aa9!'+secrets.token_urlsafe(36))
 os.chmod(f,0o600)
print('OpenSearch password files present; values not displayed.')
PY
