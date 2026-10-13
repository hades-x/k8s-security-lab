#!/usr/bin/env python3

if __name__ == '__main__':
    import os as _runtime_os
    if _runtime_os.environ.get('LAB_ALLOW_RUNTIME') != 'yes':
        raise SystemExit('BLOCKED: runtime requires LAB_ALLOW_RUNTIME=yes and tools/DEPENDENCIES.md review')
import argparse, pathlib, random, time, ipaddress, json
from scapy.all import Ether,IP,UDP,TCP,DNS,DNSQR,DNSRR,Raw,wrpcap
p=argparse.ArgumentParser();p.add_argument('--output',default='soc/traffic/pcaps');a=p.parse_args()
out=pathlib.Path(a.output);out.mkdir(parents=True,exist_ok=True);r=random.Random(20261013);packets=[];t=1700000000.0
client='192.168.150.21';server='192.168.150.22';dnsip='192.168.150.11'; sport=40000
mac1='02:00:00:00:00:21';mac2='02:00:00:00:00:22'
def add(pkt,ts,reply=False):
 pkt=Ether(src=mac2 if reply else mac1,dst=mac1 if reply else mac2)/pkt;pkt.time=ts;packets.append(pkt)
def dns(q,ts):
 ident=r.randint(1,65000)
 add(IP(src=client,dst=dnsip)/UDP(sport=43000+ident%1000,dport=53)/DNS(id=ident,rd=1,qd=DNSQR(qname=q)),ts)
 add(IP(src=dnsip,dst=client)/UDP(sport=53,dport=43000+ident%1000)/DNS(id=ident,qr=1,aa=1,qd=DNSQR(qname=q),an=DNSRR(rrname=q,rdata=server),ancount=1),ts+.02,True)
def http(host,path,ua,ts):
 global sport
 sport+=1;seq=1000;ack=2000
 req=f'GET {path} HTTP/1.1\r\nHost: {host}\r\nUser-Agent: {ua}\r\nConnection: close\r\n\r\n'.encode();response=b'HTTP/1.1 200 OK\r\nContent-Length: 2\r\nConnection: close\r\n\r\nOK'
 for dt,rev,flags,sq,aq,data in [(0,False,'S',seq,0,b''),(.01,True,'SA',ack,seq+1,b''),(.02,False,'A',seq+1,ack+1,b''),(.03,False,'PA',seq+1,ack+1,req),(.04,True,'PA',ack+1,seq+1+len(req),response),(.05,False,'FA',seq+1+len(req),ack+1+len(response),b''),(.06,True,'FA',ack+1+len(response),seq+2+len(req),b''),(.07,False,'A',seq+2+len(req),ack+2+len(response),b'')]:
  ip=IP(src=server if rev else client,dst=client if rev else server);tcp=TCP(sport=80 if rev else sport,dport=sport if rev else 80,flags=flags,seq=sq,ack=aq)
  add(ip/tcp/Raw(data) if data else ip/tcp,ts+dt,rev)
for i in range(12):
 ts=t+i*5
 dns('normal.lab.test',ts);http('normal.lab.test','/','LabBrowser/1.0',ts+.1)
 dns(f'{i:04d}.evil-c2.lab.test',ts+.3);dns('ioc.evil-c2.lab.test',ts+.4)
 http('ioc.evil-c2.lab.test','/heartbeat','LabBeacon/1.0',ts+.5)
 long=''.join(r.choice('abcdefghijklmnopqrstuvwxyz0123456789') for _ in range(60))+'.'+''.join(r.choice('abcdefghijklmnopqrstuvwxyz0123456789') for _ in range(50))+'.tunnel.lab.test'
 dns(long,ts+.6)
for i,port in enumerate(range(2000,2020)):
 add(IP(src=client,dst=server)/TCP(sport=50000+i,dport=port,flags='S',seq=100+i),t+60+i*.03)
 add(IP(src=server,dst=client)/TCP(sport=port,dport=50000+i,flags='RA',seq=0,ack=101+i),t+60+i*.03+.01,True)
for pkt in packets:
 for key in ('src','dst'):assert ipaddress.ip_address(pkt[IP].getfieldval(key)) in ipaddress.ip_network('192.168.150.0/24')
packets.sort(key=lambda x:float(x.time));wrpcap(str(out/'lab-scenarios.pcap'),packets)
print(json.dumps({'pcap':str(out/'lab-scenarios.pcap'),'packets':len(packets),'dns_queries':48,'http_sessions':24,'scanned_ports':20,'seed':20261013},sort_keys=True))
