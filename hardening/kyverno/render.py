#!/usr/bin/env python3

if __name__ == '__main__':
    import os as _runtime_os
    if _runtime_os.environ.get('LAB_ALLOW_RUNTIME') != 'yes':
        raise SystemExit('BLOCKED: runtime requires LAB_ALLOW_RUNTIME=yes and tools/DEPENDENCIES.md review')
import argparse,pathlib,sys,yaml
root=pathlib.Path(__file__).resolve().parent
parser=argparse.ArgumentParser();parser.add_argument('--mode',choices=['Audit','Enforce'],default='Audit');parser.add_argument('--signatures',action='store_true');args=parser.parse_args()
values=yaml.safe_load((root/'values.yaml').read_text());docs=[]
for f in sorted((root/'policies').glob('*.yaml')):
 p=yaml.safe_load(f.read_text())
 if p['metadata']['name']=='lab-prod-signatures':
  if not args.signatures:continue
  key=(root/'cosign.pub').read_text();assert 'BEGIN PUBLIC KEY' in key
  p['spec']['rules'][0]['verifyImages'][0]['attestors'][0]['entries'][0]['keys']['publicKeys']=key
  p['spec']['rules'][0]['verifyImages'][0]['mutateDigest']=args.mode=='Enforce'
 if p['metadata']['name']=='lab-image-registries':p['spec']['rules'][0]['validate']['foreach'][0]['pattern']['image']=' | '.join(values['labPolicy']['registries'])
 name=p['metadata']['name']
 if name=='lab-image-registries':
  p['spec']['validationFailureAction']='Audit'
  p['spec']['validationFailureActionOverrides']=[{'action':'Enforce','namespaces':['prod']}]
 elif name=='lab-prod-signatures':p['spec']['validationFailureAction']=args.mode
 else:p['spec']['validationFailureAction']=args.mode
 docs.append(p)
yaml.safe_dump_all(docs,sys.stdout,sort_keys=False)
