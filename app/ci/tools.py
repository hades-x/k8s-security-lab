
if __name__ == '__main__':
    import os as _runtime_os
    if _runtime_os.environ.get('LAB_ALLOW_RUNTIME') != 'yes':
        raise SystemExit('BLOCKED: runtime requires LAB_ALLOW_RUNTIME=yes and tools/DEPENDENCIES.md review')
"""Pinned upstream static tools; refuse checksum mismatch before executing."""
import urllib.request, pathlib, tarfile, hashlib, io
P=pathlib.Path(".ci-bin");P.mkdir(exist_ok=True)
tools=[("crane","https://github.com/google/go-containerregistry/releases/download/v0.22.1/go-containerregistry_Linux_x86_64.tar.gz","8e75c326adb43b053cfd78b9b987663f8f4fe4557f4d3915905643f25c730992"),
       ("cosign","https://github.com/sigstore/cosign/releases/download/v3.1.3/cosign-linux-amd64","4629c757b7618056f8ddd7e2625ae9fdd94c0372a65049520bc7d9df9efc7f71")]
for name,url,expected in tools:
    p=P/name
    if not p.exists():
        with urllib.request.urlopen(url,timeout=120) as r:
            if name=="crane":
                with tarfile.open(fileobj=r,mode="r|gz") as t:
                    for member in t:
                        if member.name in ("crane", "./crane"):
                            with t.extractfile(member) as source, p.open("wb") as out:
                                while chunk := source.read(1024*1024): out.write(chunk)
                            break
                    else: raise RuntimeError("Missing crane archive member")
            else:
                with p.open("wb") as out:
                    while chunk := r.read(1024*1024): out.write(chunk)
    h=hashlib.sha256()
    with p.open("rb") as source:
        while chunk := source.read(1024*1024): h.update(chunk)
    assert h.hexdigest()==expected,"Checksum mismatch: "+name
    p.chmod(0o755)
    print("PASS pinned binary checksum "+name+" "+expected)
