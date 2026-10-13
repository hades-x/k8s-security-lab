#!/usr/bin/env python3
"""Read-only stdlib candidate gate; no Git, network, deploy or shell execution.

Scans every candidate file, including untracked and gitignored files. Reports
rule identifiers, never matched payloads. Not a complete DLP or security audit.
"""
import argparse
import base64
import ipaddress
import json
import os
from pathlib import Path
import re
import stat
from urllib.parse import unquote, urlsplit

FORBIDDEN_PARTS={'.secrets','evidence','state','vendor','vendor-skills','vms','.env','.venv','.venv-sigma','node_modules'}
FORBIDDEN_NAMES={'kubeconfig','id_rsa','id_ed25519','cosign.key','cosign.pub','soc-overview-source.ndjson','soc-overview.ndjson'}
FORBIDDEN_EXT={'.pyc','.pcap','.png','.jpg','.jpeg','.pdf','.tgz','.tar','.gz','.zip','.sqlite','.db','.pem','.crt','.key'}
RULES={
 'private-key':r'-----BEGIN (?:RSA |EC |OPENSSH |ENCRYPTED )?PRIVATE KEY-----',
 'embedded-trust':r'-----BEGIN (?:CERTIFICATE|PUBLIC KEY)-----',
 'github-token':r'\b(?:gh[pousr]_[A-Za-z0-9]{20,}|github_pat_[A-Za-z0-9_]{30,})\b',
 'aws-key':r'\b(?:AKIA|ASIA)[A-Z0-9]{16}\b',
 'jwt':r'\beyJ[A-Za-z0-9_-]{20,}\.[A-Za-z0-9_-]{20,}\.[A-Za-z0-9_-]{20,}',
 'k3s-token':r'\bK10[0-9a-f]{64}::',
 'personal-path':r'/home/(?!(?:lab|step)(?:/|\b))[\w.-]+|/Users/[\w.-]+',
 'private-identity':r'(?i)\b(?:PC-[A-Za-z][\w.-]*|hlabv\d+[\w-]*|(?:k8slab|k3s)-[sa][123])\b',
 'tailnet-host':r'(?i)\b[\w.-]+\.ts\.net\b',
 'credential-url':r'https?://[^\s/]+:[^\s/@]+@',
}
COMPILED={key:re.compile(pattern) for key,pattern in RULES.items()}

def content_rules(text):
    found={key for key,p in COMPILED.items() if p.search(text)}
    for match in re.finditer(r'\b100\.\d{1,3}\.\d{1,3}\.\d{1,3}\b',text):
        try:
            if ipaddress.ip_address(match[0]) in ipaddress.ip_network('100.'+'64.0.0/10'):found.add('tailnet-address')
        except ValueError:pass
    # Literal YAML/JSON credential fields; references and explicit placeholders are allowed.
    for match in re.finditer(r'(?im)^\s*["\']?(?:password|clientSecret|api_key|access_token)["\']?\s*:\s*["\']?([^\n]+)',text):
        value=match[1].strip().strip('\"\' ,')
        if value and not any(c in value for c in ('$','{','}')) and value not in ('null','None','REGENERATE_LAB_SECRET',''):
            found.add('literal-credential')
    return found

def json_credentials(value):
    if isinstance(value,dict):
        for key,item in value.items():
            if str(key).casefold() in {'password','clientsecret','apikey','api_key','access_token','private_key'} and isinstance(item,str) and item and not any(c in item for c in ('$', '{','}')) and not item.startswith(('REGENERATE_','REPLACE_','<')):
                return True
            if json_credentials(item):return True
    elif isinstance(value,list):
        return any(json_credentials(item) for item in value)
    return False

def scan_content(text,depth=0):
    found=content_rules(text)
    if text.lstrip().startswith(('{','[')):
        try:
            if json_credentials(json.loads(text)):found.add('literal-json-credential')
        except (ValueError,RecursionError):pass
    if depth<3:
        # Standard and URL-safe base64, including two nested encodings. Bounded reads.
        for m in re.finditer(r'(?<![\w+/-])[A-Za-z0-9+/_-]{16,}={0,2}(?![\w+/-])',text):
            token=m[0]
            if len(token)>1024*1024:found.add('oversized-encoded-data');continue
            try:
                decoded=base64.b64decode(token+'='*((-len(token))%4),altchars=b'-_',validate=True).decode('utf-8')
            except (ValueError,UnicodeError):continue
            if decoded!=token:found.update(scan_content(decoded,depth+1))
    return found

def anchors(text):
    text=re.sub(r'```.*?```|~~~.*?~~~','',text,flags=re.S)
    counts={}; result=set()
    for heading in re.findall(r'^#{1,6}\s+(.+?)(?:\s+#+)?$',text,re.M):
        slug=re.sub(r'[^\w\- ]','',heading.lower()).replace(' ','-')
        n=counts.get(slug,0);counts[slug]=n+1;result.add(slug+('-'+str(n) if n else ''))
    result.update(re.findall(r'(?:id|name)=[\"\']([^\"\']+)',text))
    return result

def markdown_links(root,path,text):
    errors=[]
    text=re.sub(r'```.*?```|~~~.*?~~~','',text,flags=re.S)
    refs={m[1].lower():m[2] for m in re.finditer(r'^\s*\[([^\]]+)\]:\s*<?([^\s>]+)>?',text,re.M)}
    targets=re.findall(r'!?\[[^\]]*\]\(\s*<?([^\s)>]+)>?(?:\s+[\"\'][^\n]*?[\"\'])?\s*\)',text)
    for m in re.finditer(r'!?\[([^\]]+)\]\[([^\]]*)\]',text):
        label=(m[2] or m[1]).lower()
        if label not in refs:errors.append('undefined-link-reference')
        else:targets.append(refs[label])
    for target in targets:
        u=urlsplit(target)
        if u.scheme in ('https','http','mailto') or target.startswith('//'):continue
        if u.scheme:errors.append('unsupported-link-scheme');continue
        dest=path if not u.path else (root/u.path.lstrip('/') if u.path.startswith('/') else path.parent/unquote(u.path))
        normalized=Path(os.path.abspath(dest))
        if not normalized.is_relative_to(root):errors.append('link-escapes-tree');continue
        ancestors=[root.joinpath(*normalized.relative_to(root).parts[:i]) for i in range(1,len(normalized.relative_to(root).parts)+1)]
        if any(p.is_symlink() for p in ancestors):errors.append('link-symlink');continue
        if not normalized.exists():errors.append('broken-local-link');continue
        if u.fragment and normalized.suffix.lower()=='.md':
            if unquote(u.fragment) not in anchors(normalized.read_text()):errors.append('broken-local-anchor')
    return errors

def workflow_rules(text):
    errors=[]
    uses=re.findall(r'^\s*-?\s*uses:\s*(\S+)',text,re.M)
    if not uses or any(not re.fullmatch(r'[\w./-]+@[a-f0-9]{40}',x) for x in uses):errors.append('unpinned-action')
    if not re.search(r'^permissions:\s*\n\s+contents: read\s*$',text,re.M):errors.append('workflow-permissions')
    if re.search(r'\b(?:write|pull_request_target|secrets\.|persist-credentials:\s*true)\b',text):errors.append('workflow-authority')
    if 'timeout-minutes:' not in text:errors.append('workflow-timeout')
    return errors

def audit(root):
    root=Path(os.path.abspath(root)); errors=[]
    if root.is_symlink() or not root.is_dir():return [('.', 'invalid-root')]
    for base,dirs,files in os.walk(root,followlinks=False):
        for name in dirs+files:
            p=Path(base)/name;rel=str(p.relative_to(root))
            if p.is_symlink():errors.append((rel,'symlink'))
        # Git metadata is not publication content; reject cache binaries too.
        dirs[:]=[d for d in dirs if d != '.git' and not (Path(base)/d).is_symlink()]
        for name in files:
            p=Path(base)/name;rel=str(p.relative_to(root))
            if p.is_symlink():continue
            st=p.lstat()
            if not stat.S_ISREG(st.st_mode):errors.append((rel,'special-file'));continue
            if st.st_nlink!=1:errors.append((rel,'hardlink'))
            if any(x in FORBIDDEN_PARTS for x in p.relative_to(root).parts) or name in FORBIDDEN_NAMES or p.suffix.lower() in FORBIDDEN_EXT:errors.append((rel,'forbidden-artifact'))
            if st.st_size>4*1024*1024:errors.append((rel,'oversized-file'));continue
            try:text=p.read_text(encoding='utf-8')
            except (UnicodeError,OSError):errors.append((rel,'unreadable-text'));continue
            if '\x00' in text:errors.append((rel,'binary'))
            errors.extend((rel,rule) for rule in sorted(scan_content(text)))
            if p.suffix=='.md':errors.extend((rel,rule) for rule in markdown_links(root,p,text))
            if '.github/workflows/' in rel and p.suffix in ('.yaml','.yml'):errors.extend((rel,rule) for rule in workflow_rules(text))
    return sorted(set(errors))

def main():
    parser=argparse.ArgumentParser(description=__doc__);parser.add_argument('root',nargs='?',default=str(Path(__file__).resolve().parent.parent));a=parser.parse_args()
    errors=audit(a.root)
    print(json.dumps({'passed':not errors,'finding_count':len(errors),'findings':[{'path':p,'rule':r} for p,r in errors]},indent=2))
    return bool(errors)

if __name__=='__main__':raise SystemExit(main())
