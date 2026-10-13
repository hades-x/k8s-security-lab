
if __name__ == '__main__':
    import os as _runtime_os
    if _runtime_os.environ.get('LAB_ALLOW_RUNTIME') != 'yes':
        raise SystemExit('BLOCKED: runtime requires LAB_ALLOW_RUNTIME=yes and tools/DEPENDENCIES.md review')
import os,subprocess,pathlib,json
os.chdir('/data/k8s-lab');os.environ['LC_ALL']='C'
code='''from pathlib import Path
from collections import Counter
c=Counter()
for p in Path('/proc').iterdir():
 if not p.name.isdigit():continue
 try:
  uid=int((p/'status').read_text().split('Uid:')[1].split()[0])
  c[uid]+=sum('inotify' in str(f.resolve()) for f in (p/'fd').iterdir())
 except (FileNotFoundError,PermissionError,ProcessLookupError):pass
print('inotify instances per UID',dict(c));print(Path('/proc/sys/fs/inotify/max_user_instances').read_text().strip())
'''
for n in ['s1','s2','s3','a1','a2']:
 print('lab-'+n,flush=True);r=subprocess.run(['scripts/ssh-node.sh','lab-'+n,'export LC_ALL=C; sudo python3 -'],input=code,text=True,capture_output=True);print(r.stdout,r.stderr)
