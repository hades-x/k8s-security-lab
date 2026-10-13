
if __name__ == '__main__':
    import os as _runtime_os
    if _runtime_os.environ.get('LAB_ALLOW_RUNTIME') != 'yes':
        raise SystemExit('BLOCKED: runtime requires LAB_ALLOW_RUNTIME=yes and tools/DEPENDENCIES.md review')
from pathlib import Path
root=Path('/data/k8s-lab')
p=root/'audits/summarize.py';s=p.read_text().replace("def load(name):return json.loads((root/name).read_text())", "def load(name):\n text=(root/name).read_text();start=text.find('{');return json.loads(text[start:])")
p.write_text(s)
p=root/'hardening/rbac/audit-secrets.py';s=p.read_text().replace("r.get('rules',[])","(r.get('rules') or [])").replace("b.get('subjects',[])","(b.get('subjects') or [])");p.write_text(s)
p=root/'hardening/kyverno/install.sh';s=p.read_text().replace('-f "$ROOT/hardening/kyverno/values.yaml" --wait','-f "$ROOT/hardening/kyverno/values.yaml" -f "$ROOT/devsecops/kyverno-registry-values.yaml" --wait');p.write_text(s)
p=root/'hardening/pss/install.sh';s=p.read_text().replace('kubectl apply -f "$ROOT/hardening/pss/budgets.yaml"','python3 "$ROOT/hardening/pss/apply-budgets.py"');p.write_text(s)
(root/'hardening/pss/apply-budgets.py').write_text('''#!/usr/bin/env python3
import subprocess,yaml,pathlib,json
root=pathlib.Path(__file__).resolve().parent
for d in yaml.safe_load_all((root/'budgets.yaml').read_text()):
 ns=d['metadata']['namespace'];kind=d['kind']
 current=json.loads(subprocess.check_output(['kubectl','get',kind,'-n',ns,'-o','json']))
 if current['items'] and ns!='demo':
  print('Preserved P6 '+kind+' in '+ns);continue
 subprocess.run(['kubectl','apply','-f','-'],input=yaml.safe_dump(d),text=True,check=True)
''')
print('Fixed kube-bench warning preamble and null RBAC rules; preserved P6 budgets.')
