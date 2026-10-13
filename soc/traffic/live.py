
if __name__ == '__main__':
    import os as _runtime_os
    if _runtime_os.environ.get('LAB_ALLOW_RUNTIME') != 'yes':
        raise SystemExit('BLOCKED: runtime requires LAB_ALLOW_RUNTIME=yes and tools/DEPENDENCIES.md review')
import os, socket, threading, struct, time, urllib.request
from http.server import HTTPServer,BaseHTTPRequestHandler
class H(BaseHTTPRequestHandler):
 def do_GET(self):self.send_response(200);self.end_headers();self.wfile.write(b'lab only')
 def log_message(self,*a):pass
def dns_server():
 s=socket.socket(socket.AF_INET,socket.SOCK_DGRAM);s.bind(('0.0.0.0',8053))
 while True:
  data,addr=s.recvfrom(4096)
  if len(data)>=12:s.sendto(data[:2]+b'\x81\x83'+data[4:6]+b'\x00'*6+data[12:],addr)
if os.getenv('ROLE')=='server':
 threading.Thread(target=dns_server,daemon=True).start();HTTPServer(('0.0.0.0',8080),H).serve_forever()
else:
 target=socket.gethostbyname('lab-web.soc-traffic.svc.cluster.local')
 import ipaddress
 assert ipaddress.ip_address(target) in ipaddress.ip_network('10.43.0.0/16')
 for i in range(100000):
  name=(f'{i%100:04d}.evil-c2.lab.test' if os.getenv('BEACON')=='true' else 'normal.lab.test')
  q=b''.join(bytes([len(x)])+x.encode() for x in name.split('.'))+b'\0'
  s=socket.socket(socket.AF_INET,socket.SOCK_DGRAM);s.settimeout(2);s.sendto(struct.pack('!HHHHHH',i%65536,256,1,0,0,0)+q+b'\x00\x01\x00\x01',(target,53))
  try:s.recvfrom(4096)
  except TimeoutError:pass
  s.close()
  try:urllib.request.urlopen(urllib.request.Request('http://'+target+':8080/heartbeat',headers={'User-Agent':'LabBeacon/1.0' if os.getenv('BEACON')=='true' else 'LabBrowser/1.0'}),timeout=2).read()
  except Exception:pass
  time.sleep(5)
