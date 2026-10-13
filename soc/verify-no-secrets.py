#!/usr/bin/env python3

if __name__ == '__main__':
    import os as _runtime_os
    if _runtime_os.environ.get('LAB_ALLOW_RUNTIME') != 'yes':
        raise SystemExit('BLOCKED: runtime requires LAB_ALLOW_RUNTIME=yes and tools/DEPENDENCIES.md review')
"""Check public SOC artifacts against actual generated credentials, without echoing them."""
from pathlib import Path
import base64,json,subprocess
ROOT=Path('/data/k8s-lab')
values=[p.read_bytes().strip() for p in (ROOT/'.secrets').glob('opensearch-*.password')]
values.extend(v.encode() for k,v in (line.split('=',1) for line in (ROOT/'.secrets/misp.env').read_text().splitlines()))
for name in ['zeek-shipper','audit-shipper','soc-indexer','falcosidekick']:
    secret=json.loads(subprocess.check_output(['kubectl','-n','kafka','get','secret',name,'-o','json']))
    values.append(base64.b64decode(secret['data']['password']))
files=[p for folder in [ROOT/'soc',ROOT/'evidence/p4'] for p in folder.rglob('*') if p.is_file() and p.suffix not in ['.pcap','.pyc']]
files+=list((ROOT/'tests').glob('phase-p4*.sh'))
leaks=[str(p.relative_to(ROOT)) for p in files if any(v and v in p.read_bytes() for v in values)]
result={'checked_files':len(files),'credential_values_checked':len(values),'leaked_paths':leaks}
print(json.dumps(result,indent=2))
assert not leaks,'Generated credentials found in public artifacts; do not commit them'
