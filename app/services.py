"""Three processes, one small immutable image. External I/O is integration-tested."""
import json, os, ssl, sys, time, uuid, threading, urllib.request, urllib.error
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from domain import normalize_order

ROLE = os.environ.get("ROLE", "web")
ENV = os.environ.get("ENVIRONMENT", "dev")
VERSION = os.environ.get("BUILD_REVISION", "development")
STATE = {"ready": False}

def kafka_options():
    return dict(bootstrap_servers=os.environ["KAFKA_BOOTSTRAP"].split(","),
                security_protocol="SASL_SSL", sasl_mechanism="SCRAM-SHA-512",
                sasl_plain_username="demo-app", sasl_plain_password=os.environ["KAFKA_PASSWORD"],
                ssl_context=ssl.create_default_context(cafile="/var/run/kafka/ca.crt"),
                api_version=(4, 0, 0), request_timeout_ms=20000)

def database():
    import psycopg
    return psycopg.connect(connect_timeout=10)

def cache():
    import redis
    return redis.Redis(host=os.environ.get("VALKEY_HOST", "valkey"), decode_responses=True,
                       socket_connect_timeout=5, socket_timeout=5)

def consume():
    from kafka import KafkaConsumer
    while True:
        try:
            client = cache(); client.ping()
            consumer = KafkaConsumer("demo-orders", group_id="demo-app-" + ENV,
                                     auto_offset_reset="earliest", enable_auto_commit=False,
                                     value_deserializer=lambda b: json.loads(b.decode()), **kafka_options())
            STATE["ready"] = True
            for record in consumer:
                order = record.value
                if order.get("environment") == ENV:
                    client.set("order:" + ENV + ":" + order["id"], json.dumps(order), ex=86400)
                    print(json.dumps({"event":"cached", "id":order["id"], "partition":record.partition,
                                      "offset":record.offset, "environment":ENV}), flush=True)
                consumer.commit()
        except Exception as e:
            STATE["ready"] = False
            print(json.dumps({"event":"worker-retry", "error_type":type(e).__name__}), flush=True)
            time.sleep(5)

class Handler(BaseHTTPRequestHandler):
    def respond(self, code, value, mime="application/json"):
        data = json.dumps(value).encode() if mime == "application/json" else value.encode()
        self.send_response(code); self.send_header("Content-Type", mime)
        self.send_header("Content-Length", str(len(data))); self.end_headers(); self.wfile.write(data)
    def do_GET(self):
        if self.path == "/healthz":
            return self.respond(200 if STATE["ready"] else 503,
                                {"role":ROLE, "environment":ENV, "ready":STATE["ready"], "revision":VERSION})
        if ROLE == "web":
            if self.path.startswith("/api/orders"):
                return self.proxy()
            if self.path != "/": return self.respond(404, {"error":"not found"})
            return self.respond(200, """<!doctype html><html><head><title>Signed orders lab</title>
            <style>body{font:18px system-ui;max-width:900px;margin:3em auto;background:#101827;color:#dbeafe}
            button,input{font:inherit;padding:.5em}pre{white-space:pre-wrap}</style></head>
            <body><h1>Signed orders / DevSecOps lab</h1><p>Environment: """ + ENV + " | Revision: " + VERSION + """</p>
            <p>Forgejo → Woodpecker → Kaniko → Trivy → zot → Cosign → GitOps → Argo CD</p>
            <input id='item' value='training laptop'><button onclick='order()'>Create order</button><pre id='result'></pre>
            <script>async function order(){let r=await fetch('/api/orders',{method:'POST',headers:{'Content-Type':'application/json'},
            body:JSON.stringify({item:document.getElementById('item').value,quantity:1})});let o=await r.json();
            document.getElementById('result').textContent=JSON.stringify(o,null,2);if(r.ok)setTimeout(async()=>{
            let s=await fetch('/api/orders/'+o.id);document.getElementById('result').textContent=JSON.stringify(await s.json(),null,2)},2000)}</script></body></html>""", "text/html")
        if ROLE == "orders-api" and self.path.startswith("/orders/"):
            identifier=self.path[len("/orders/"):]
            try:
                uuid.UUID(identifier)
                with database() as db:
                    row=db.execute("SELECT id,item,quantity,environment,published FROM orders WHERE id=%s AND environment=%s",
                                   (identifier,ENV)).fetchone()
                if row is None: return self.respond(404,{"error":"order not found"})
                cached=cache().get("order:"+ENV+":"+identifier)
                return self.respond(200,{"id":row[0],"item":row[1],"quantity":row[2],"environment":row[3],
                                         "published":row[4],"cached":cached is not None,"cache":json.loads(cached) if cached else None})
            except ValueError: return self.respond(400,{"error":"invalid order id"})
            except Exception as e:
                print("GET failure "+type(e).__name__,flush=True);return self.respond(503,{"error":"dependency unavailable"})
        return self.respond(404,{"error":"not found"})
    def proxy(self):
        path=self.path[len("/api"):]
        data=None
        if self.command=="POST":
            n=int(self.headers.get("Content-Length","0"))
            if not 0<n<=8192:return self.respond(413,{"error":"payload size"})
            data=self.rfile.read(n)
        req=urllib.request.Request(os.environ.get("API_URL","http://orders-api:8080")+path,
                                   data=data,method=self.command,headers={"Content-Type":"application/json"})
        try:
            with urllib.request.urlopen(req,timeout=30) as r:return self.respond(r.status,json.load(r))
        except urllib.error.HTTPError as e:return self.respond(e.code,json.load(e))
        except Exception:return self.respond(503,{"error":"orders-api unavailable"})
    def do_POST(self):
        if ROLE=="web" and self.path=="/api/orders":return self.proxy()
        if ROLE!="orders-api" or self.path!="/orders":return self.respond(404,{"error":"not found"})
        try:
            n=int(self.headers.get("Content-Length","0"))
            if not 0<n<=8192:return self.respond(413,{"error":"payload size"})
            payload=json.loads(self.rfile.read(n)); order=normalize_order(payload,str(uuid.uuid4()),ENV)
        except (ValueError,TypeError,AttributeError):return self.respond(400,{"error":"invalid order"})
        try:
            with database() as db:
                db.execute("INSERT INTO orders(id,item,quantity,environment) VALUES (%s,%s,%s,%s)",
                           (order["id"],order["item"],order["quantity"],ENV))
            PRODUCER.send("demo-orders",key=order["id"].encode(),value=order).get(timeout=30)
            with database() as db:db.execute("UPDATE orders SET published=true WHERE id=%s",(order["id"],))
            print(json.dumps({"event":"published", "id":order["id"], "environment":ENV}),flush=True)
            return self.respond(201,order)
        except Exception as e:
            print("POST failure "+type(e).__name__,flush=True);return self.respond(503,{"error":"dependency unavailable", "id":order["id"]})

if __name__=="__main__":
    if ROLE=="orders-api":
        from kafka import KafkaProducer
        while True:
            try:
                with database() as db:db.execute("CREATE TABLE IF NOT EXISTS orders (id text PRIMARY KEY,item text NOT NULL,quantity integer NOT NULL,environment text NOT NULL,published boolean NOT NULL DEFAULT false,created_at timestamptz NOT NULL DEFAULT now())")
                PRODUCER=KafkaProducer(value_serializer=lambda v:json.dumps(v).encode(),acks="all",**kafka_options())
                cache().ping();STATE["ready"]=True;break
            except Exception as e:
                print("API initialization retry "+type(e).__name__,flush=True);time.sleep(5)
    elif ROLE=="orders-worker":threading.Thread(target=consume,daemon=True).start()
    else:STATE["ready"]=True
    ThreadingHTTPServer(("0.0.0.0",8080),Handler).serve_forever()
