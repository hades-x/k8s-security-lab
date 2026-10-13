#!/usr/bin/env python3

if __name__ == '__main__':
    import os as _runtime_os
    if _runtime_os.environ.get('LAB_ALLOW_RUNTIME') != 'yes':
        raise SystemExit('BLOCKED: runtime requires LAB_ALLOW_RUNTIME=yes and tools/DEPENDENCIES.md review')
"""Merge JSON streams with inode/content checkpoints and bounded rotation.

At-least-once, not transactional: a crash between output append and checkpoint
can duplicate a record. Fingerprints prevent inode reuse silently skipping data.
"""
import os, json, time, pathlib, hashlib
src=pathlib.Path(os.getenv('SOURCE_DIR','/streams'))
dst=pathlib.Path(os.getenv('OUTPUT_DIR','/var/log/zeek/current'))
dst.mkdir(parents=True,exist_ok=True)
statefile=dst/'.merge-state.json'
try:
    state=json.loads(statefile.read_text())
except (FileNotFoundError,ValueError):
    state={}
while True:
    present=set()
    for path in sorted(src.glob('*/*.log*')):
        if not path.is_file() or path.name.startswith(('loaded_scripts','reporter','stats','packet_filter')):
            continue
        try:
            st=path.stat()
            with path.open('rb') as peek:
                first=peek.readline()
            if not first.endswith(b'\n'):
                continue
            key=f'{st.st_dev}:{st.st_ino}:'+hashlib.sha256(first).hexdigest()
            present.add(key)
            offset=state.get(key,0)
            if st.st_size<offset:
                offset=0
            typ=path.name.split('.')[0]
            if not typ.replace('_','').isalnum():
                continue
            with path.open('rb') as inp:
                inp.seek(offset)
                while True:
                    start=inp.tell()
                    line=inp.readline()
                    if not line or not line.endswith(b'\n'):
                        inp.seek(start)
                        break
                    try:
                        record=json.loads(line)
                    except ValueError:
                        continue
                    if not isinstance(record,dict):
                        continue
                    record['sensor']=path.parent.name
                    record['capture_source']=path.parent.name
                    out=dst/(typ+'.log')
                    if out.exists() and out.stat().st_size>32*1024*1024:
                        for i in range(3,0,-1):
                            a=dst/(typ+'.log.'+str(i))
                            b=dst/(typ+'.log.'+str(i+1))
                            if i==3:
                                a.unlink(missing_ok=True)
                            elif a.exists():
                                a.replace(b)
                        out.replace(dst/(typ+'.log.1'))
                    with out.open('a') as f:
                        f.write(json.dumps(record,separators=(',',':'))+'\n')
                state[key]=inp.tell()
        except FileNotFoundError:
            # A rotation/unlink race is retried next poll, never fatal.
            continue
    state={k:v for k,v in state.items() if k in present}
    tmp=statefile.with_suffix('.tmp')
    tmp.write_text(json.dumps(state))
    tmp.replace(statefile)
    for p in src.glob('*/*.log*'):
        try:
            if p.is_file() and p.name != p.name.split('.')[0]+'.log' and time.time()-p.stat().st_mtime>7200:
                p.unlink()
        except FileNotFoundError:
            pass
    if os.getenv('MERGE_ONCE')=='1':
        break
    time.sleep(1)
