#!/usr/bin/env python3

if __name__ == '__main__':
    import os as _runtime_os
    if _runtime_os.environ.get('LAB_ALLOW_RUNTIME') != 'yes':
        raise SystemExit('BLOCKED: runtime requires LAB_ALLOW_RUNTIME=yes and tools/DEPENDENCIES.md review')
"""Reverify an already restored, labelled fixture without deleting anything."""
import pathlib,subprocess,json,re
R=pathlib.Path('/data/k8s-lab');k=str(R/'bin/kubectl')
def obj(args):return json.loads(subprocess.check_output([k]+args+['-o','json']))
ns=obj(['get','namespace','drill']);assert ns['metadata']['labels']['lab-phase']=='p3-drill'
files=sorted((R/'evidence/p3').glob('drill-*.txt'));assert files,'No completed drill evidence'
data=dict(line.split('=',1) for line in files[-1].read_text().splitlines() if '=' in line);run=data['backup'].split()[0]
assert data['before_sha256']==data['after_sha256'] and data['checksum_equal']=='true'
for kind in ['backup.velero.io','restore.velero.io']:
 d=obj(['-n','velero','get',kind,run]);assert d['status']['phase']=='Completed'
for kind,label in [('podvolumebackups','backup'),('podvolumerestores','restore')]:
 items=obj(['-n','velero','get',kind,'-l',f'velero.io/{label}-name={run}'])['items'];assert items and all(i['status']['phase']=='Completed' for i in items)
actual=subprocess.check_output([k,'-n','drill','exec','deployment/data','--','sha256sum','/data/payload']).decode().split()[0];assert actual==data['before_sha256']
print(f'PASS: read-back verification of real completed backup/delete/restore drill {run}; Deployment+PVC restored; all PodVolumeBackup/Restore Completed\nbefore_sha256={data["before_sha256"]}\nafter_sha256={actual}\nchecksum_equal=true')
