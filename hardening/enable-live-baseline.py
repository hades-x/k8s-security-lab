
if __name__ == '__main__':
    import os as _runtime_os
    if _runtime_os.environ.get('LAB_ALLOW_RUNTIME') != 'yes':
        raise SystemExit('BLOCKED: runtime requires LAB_ALLOW_RUNTIME=yes and tools/DEPENDENCIES.md review')
from pathlib import Path
import yaml,json,subprocess,copy
root=Path('/data/k8s-lab')
p=root/'hardening/kyverno/policies/lab-no-default-token.yaml';d=yaml.safe_load(p.read_text())
d['spec']['rules'][0]['preconditions']={'all':[{'key':"{{ request.object.spec.serviceAccountName || 'default' }}",'operator':'Equals','value':'default'}]}
d['spec']['rules'][0]['validate']['message']='Default service-account Pods must explicitly disable token automount; named API clients are audited through RBAC'
p.write_text(yaml.safe_dump(d,sort_keys=False))
p=root/'hardening/kyverno/render.py';s=p.read_text().replace("elif name=='lab-prod-signatures':p['spec']['validationFailureAction']='Audit'","elif name=='lab-prod-signatures':p['spec']['validationFailureAction']=args.mode");p.write_text(s)
# Admission is now Ready; only insert a skip-gated Audit placeholder if P6 has
# not installed the real policy yet. Never overwrite a P6 Enforce policy.
r=subprocess.run(['kubectl','get','clusterpolicy','lab-prod-signatures','-o','name','--ignore-not-found'],capture_output=True)
if r.returncode:raise RuntimeError('Cannot verify P6 signature policy state; refusing to write')
if not r.stdout.strip():
 d=yaml.safe_load((root/'hardening/kyverno/policies/lab-prod-signatures.yaml').read_text())
 d['metadata']['annotations']['lab.k8s/p6-signature-gate']='pending-real-signing-key'
 d['spec']['failurePolicy']='Ignore'
 d['spec']['rules'][0]['verifyImages'][0]['mutateDigest']=False
 d['spec']['rules'][0]['preconditions']={'all':[{'key':"{{ request.operation || 'BACKGROUND' }}",'operator':'Equals','value':'P6_SIGNING_READY'}]}
 subprocess.run(['kubectl','apply','-f','-'],input=yaml.safe_dump(d),text=True,check=True)
else:print('Preserved existing P6 signature policy')
p=root/'hardening/pss/EXEMPTIONS.md';s=p.read_text();s+='\nThe `lab-no-default-token` rule applies to default service-account Pods. Named service-account API clients (notably P6 CloudNativePG initdb/instance-manager Pods using `demo-db`) are not forced to disable their required Kubernetes token. This narrowly changes the prepared all-token rule to the policy name\'s actual default-token scope, prevents breaking the parallel database operator, and does not grant any RBAC permissions. Their direct Secret access remains enumerated in the secrets-reader audit. Workload creators can select service accounts, so indirect Secret access remains a documented limitation.\n';p.write_text(s)
p=root/'evidence/p5/P6-coordination.md';s=p.read_text();s+='\nUPDATE: P5 recovered Kyverno by supplying the existing public CA certificate through chart global.caCertificates.data in hardening/kyverno/values.yaml; both value files were passed to the upgrade, all three controllers are Ready. No changes were made to the P6 values file. The chart\'s data path adds the required subPath. The token policy now enforces only default service-account Pods to preserve CNPG named API clients. A skip-gated Audit signature placeholder exists until P6 applies its real key/policy; applying the original signature manifest/render with SIGNATURES=true removes the gate.\n';p.write_text(s)
print('Default tokens enforced without breaking named CNPG API clients; signature Audit placeholder is gated for P6.')
