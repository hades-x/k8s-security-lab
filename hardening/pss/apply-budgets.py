#!/usr/bin/env python3

if __name__ == '__main__':
    import os as _runtime_os
    if _runtime_os.environ.get('LAB_ALLOW_RUNTIME') != 'yes':
        raise SystemExit('BLOCKED: runtime requires LAB_ALLOW_RUNTIME=yes and tools/DEPENDENCIES.md review')
import subprocess,yaml,pathlib,json
root=pathlib.Path(__file__).resolve().parent
for d in yaml.safe_load_all((root/'budgets.yaml').read_text()):
 ns=d['metadata']['namespace'];kind=d['kind']
 current=json.loads(subprocess.check_output(['kubectl','get',kind,'-n',ns,'-o','json']))
 if current['items'] and ns!='demo':
  print('Preserved P6 '+kind+' in '+ns);continue
 subprocess.run(['kubectl','apply','-f','-'],input=yaml.safe_dump(d),text=True,check=True)
