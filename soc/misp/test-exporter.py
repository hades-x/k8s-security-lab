#!/usr/bin/env python3
from pathlib import Path
import json,subprocess,sys,tempfile
script=Path(__file__).with_name('misp-to-zeek-intel.py');fixture=Path(__file__).parent/'fixtures/lab-event.json'
with tempfile.TemporaryDirectory(dir='evidence/p4-prep-b') as tmp:
 out=Path(tmp)/'misp.intel';subprocess.run([sys.executable,str(script),'--from-json',str(fixture),'--output',str(out)],check=True)
 lines=out.read_text().splitlines();assert len(lines)==5 and len(set(lines[1:]))==4
 assert any(x.startswith('192.168.150.22\tIntel::ADDR') for x in lines)
 assert any(x.startswith('ioc.evil-c2.lab.test\tIntel::DOMAIN') for x in lines)
 assert any(x.startswith('ioc.evil-c2.lab.test/heartbeat\tIntel::URL') for x in lines)
 assert all(len(x.split('\t'))==5 and x.endswith('\tT') for x in lines[1:])
 evidence=Path('evidence/p4-prep-b/exported-misp.intel');evidence.write_text(out.read_text())
 empty=Path(tmp)/'empty.json';empty.write_text('{"response":{"Attribute":[]}}');subprocess.run([sys.executable,str(script),'--from-json',str(empty),'--output',str(out)],check=True);assert len(out.read_text().splitlines())==1
print('PASS exporter: 4 unique indicators, ADDR/DOMAIN/URL, URL scheme removed, notice enabled, header-only empty fixture')
