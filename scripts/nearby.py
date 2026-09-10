"""On-demand LocalSend v2 upload subset for Skill-Desk packages.

The LAN server never exposes the management API. Only the loopback controller
can approve offers, select exports or stage received packages for installation.
"""
import base64
from datetime import datetime, timedelta, timezone
import hashlib
import http.client
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
import ipaddress
import json
from pathlib import Path
import re
import secrets
import socket
import ssl
import tempfile
import threading
import time
from urllib.parse import parse_qs, urlsplit, urlencode

import psutil
from skill_packages import MAX_BYTES

GROUP, DISCOVERY_PORT = '224.0.0.167', 53317
PREFIX = '/api/localsend/v2/'
NETWORKS = tuple(ipaddress.ip_network(n) for n in ('10.0.0.0/8', '172.16.0.0/12', '192.168.0.0/16', '169.254.0.0/16', '127.0.0.0/8'))


def local_ip(value):
    try:
        address = ipaddress.ip_address(value)
        return isinstance(address, ipaddress.IPv4Address) and any(address in n for n in NETWORKS)
    except ValueError: return False


def addresses():
    return sorted({a.address for items in psutil.net_if_addrs().values() for a in items
                   if a.family == socket.AF_INET and local_ip(a.address) and not a.address.startswith('127.')})


def label(value):
    return ''.join(c for c in str(value)[:60] if c.isprintable()).strip() or 'Nearby device'


def security_code(fingerprint):
    return ' '.join(fingerprint[i:i+4].upper() for i in range(0, 16, 4))


def certificate(directory):
    from cryptography import x509
    from cryptography.hazmat.primitives import hashes, serialization
    from cryptography.hazmat.primitives.asymmetric import ec
    from cryptography.x509.oid import NameOID
    key = ec.generate_private_key(ec.SECP256R1())
    name = x509.Name([x509.NameAttribute(NameOID.COMMON_NAME, 'Skill-Desk nearby session')])
    now = datetime.now(timezone.utc)
    cert = (x509.CertificateBuilder().subject_name(name).issuer_name(name).public_key(key.public_key())
            .serial_number(x509.random_serial_number()).not_valid_before(now-timedelta(minutes=1))
            .not_valid_after(now+timedelta(days=1)).sign(key, hashes.SHA256()))
    cert_path, key_path = Path(directory)/'certificate.pem', Path(directory)/'key.pem'
    cert_path.write_bytes(cert.public_bytes(serialization.Encoding.PEM))
    with key_path.open('xb') as out:
        key_path.chmod(0o600)
        out.write(key.private_bytes(serialization.Encoding.PEM, serialization.PrivateFormat.PKCS8, serialization.NoEncryption()))
    context = ssl.SSLContext(ssl.PROTOCOL_TLS_SERVER)
    context.minimum_version = ssl.TLSVersion.TLSv1_2
    context.load_cert_chain(cert_path, key_path)
    key_path.unlink(); cert_path.unlink()  # The session key remains only in the TLS context.
    return context, cert.fingerprint(hashes.SHA256()).hex()


class LanServer(ThreadingHTTPServer):
    daemon_threads = True
    allow_reuse_address = False

    def process_request(self, request, client_address):
        if not local_ip(client_address[0]) or not self.slots.acquire(blocking=False):
            request.close(); return
        with self.owner.lock: self.owner.sockets.add(request)
        try: super().process_request(request, client_address)
        except Exception:
            self.slots.release(); request.close(); raise

    def process_request_thread(self, request, client_address):
        original = request
        try:
            request.settimeout(3)
            request = self.context.wrap_socket(request, server_side=True)
            with self.owner.lock:
                self.owner.sockets.discard(original)
                if self.owner.stopped.is_set(): request.close(); return
                self.owner.sockets.add(request)
            request.settimeout(15)
            self.finish_request(request, client_address)
        except (OSError, ValueError): pass
        finally:
            with self.owner.lock:
                self.owner.sockets.discard(original); self.owner.sockets.discard(request)
            self.shutdown_request(request)
            self.slots.release()


class Session:
    def __init__(self, mode, *, bind='0.0.0.0', port=53317, discover=True):
        if mode not in {'send', 'receive'}: raise ValueError('Choose Send or Receive.')
        self.mode = mode
        self.lock = threading.RLock()
        self.stopped = threading.Event()
        self.sockets = set()
        self.peers = {}
        self.pending = None
        self.received = None
        self.phase, self.message, self.progress = 'ready', '', 0
        self.warning = ''
        self.created = self.touched = time.monotonic()
        self.pin_attempts = 0
        self.pin = f'{secrets.randbelow(1000000):06d}'
        self.alias = 'Skill-Desk '+secrets.token_hex(2).upper()
        self.temp = tempfile.TemporaryDirectory(prefix='skilldesk-nearby-')
        self.udp = None
        self.server = None
        try:
            context, self.fingerprint = certificate(self.temp.name)
            owner = self
            class Handler(BaseHTTPRequestHandler):
                def log_message(self, *_): pass
                def do_GET(self): self.dispatch()
                def do_POST(self): self.dispatch()
                def reply(self, code, value=None):
                    content = b'' if value is None else json.dumps(value).encode()
                    self.send_response(code)
                    self.send_header('Content-Type', 'application/json')
                    self.send_header('Content-Length', str(len(content)))
                    self.send_header('Connection', 'close')
                    self.end_headers(); self.wfile.write(content)
                def body(self, limit=16384):
                    size = int(self.headers.get('Content-Length', '-1'))
                    if self.headers.get('Transfer-Encoding') or not 0 <= size <= limit: raise ValueError('Invalid request size.')
                    data = self.rfile.read(size)
                    if len(data) != size: raise ValueError('Incomplete request.')
                    value = json.loads(data)
                    if not isinstance(value, dict): raise ValueError('Expected an object.')
                    return value
                def dispatch(self):
                    try:
                        if self.headers.get('Origin') or owner.stopped.is_set(): self.reply(403); return
                        url = urlsplit(self.path)
                        route = url.path.removeprefix(PREFIX) if url.path.startswith(PREFIX) else ''
                        query = {k: v[0] for k,v in parse_qs(url.query).items()}
                        if self.command == 'GET' and route == 'info': self.reply(200, owner.info()); return
                        if self.command != 'POST': self.reply(404); return
                        if route == 'register':
                            self.body(); self.reply(200, owner.info()); return
                        if route == 'prepare-upload': owner.offer(self, query); return
                        if route == 'upload': owner.upload(self, query); return
                        if route == 'cancel':
                            with owner.lock:
                                pending = owner.pending
                                if not pending or pending['ip'] != self.client_address[0] or query.get('sessionId') != pending['id']:
                                    self.reply(403); return
                                pending['decision'] = False; pending['event'].set()
                                owner.pending = None
                                owner.phase, owner.message = 'failed', 'Sender cancelled the transfer.'
                            self.reply(200); return
                        self.reply(404)
                    except (ValueError, KeyError, TypeError, json.JSONDecodeError): self.reply(400)
                    except (OSError, TimeoutError): pass
            try: self.server = LanServer((bind, port), Handler)
            except OSError:
                if port != 53317: raise
                self.server = LanServer((bind, 0), Handler)
            self.server.context, self.server.owner = context, self
            self.server.slots = threading.BoundedSemaphore(8)
            self.port = self.server.server_address[1]
            threading.Thread(target=self.server.serve_forever, kwargs={'poll_interval':.1}, daemon=True).start()
            if discover: self.start_discovery()
            threading.Thread(target=self.watch_expiry, daemon=True).start()
        except Exception:
            self.stop(); raise

    def info(self, announce=False):
        return {'alias':self.alias, 'version':'2.2', 'deviceModel':'Skill-Desk', 'deviceType':'desktop',
                'fingerprint':self.fingerprint, 'port':self.port, 'protocol':'https', 'download':False,
                'announce':announce, 'skilldeskMode':self.mode}

    def snapshot(self):
        with self.lock:
            self.touched = time.monotonic()
            self.peers = {k:v for k,v in self.peers.items() if v.get('manual') or self.touched-v['seen'] < 30}
            pending = self.pending
            return {'active':not self.stopped.is_set(), 'mode':self.mode, 'alias':self.alias,
                    'pin':self.pin if self.mode=='receive' else '', 'code':security_code(self.fingerprint),
                    'port':self.port, 'addresses':[f'{ip}:{self.port}' for ip in addresses()], 'phase':self.phase,
                    'message':self.message, 'warning':self.warning, 'progress':self.progress,
                    'peers':[{k:v for k,v in peer.items() if k!='seen'} for peer in self.peers.values()],
                    'incoming':{'id':pending['id'],'alias':pending['alias'],'ip':pending['ip'],'size':pending['size']} if pending else None}

    def watch_expiry(self):
        while not self.stopped.wait(2):
            with self.lock:
                if self.pending and self.pending['deadline'] and time.monotonic()>self.pending['deadline']:
                    self.pending=None; self.phase='failed'; self.message='Transfer timed out. No skills were installed.'
                expired = time.monotonic()-self.touched > 60 or time.monotonic()-self.created > 600
            if expired: self.stop(); return

    def stop(self):
        self.stopped.set()
        with self.lock:
            if self.pending: self.pending['decision']=False; self.pending['event'].set()
            sockets = list(self.sockets)
            self.received = None
        if self.udp:
            try: self.udp.close()
            except OSError: pass
        for sock in sockets:
            try: sock.shutdown(socket.SHUT_RDWR)
            except OSError: pass
            try: sock.close()
            except OSError: pass
        if self.server:
            self.server.shutdown(); self.server.server_close()
        self.temp.cleanup()

    def add_peer(self, ip, info, manual=False):
        if not local_ip(ip) or info.get('protocol')!='https' or info.get('skilldeskMode')!='receive': return
        fp, port = info.get('fingerprint'), info.get('port')
        if not isinstance(fp,str) or not re.fullmatch('[a-f0-9]{64}',fp) or type(port)!=int or not 1<=port<=65535 or fp==self.fingerprint: return
        key = fp+'@'+ip+':'+str(port)
        with self.lock:
            if len(self.peers)>=100 and key not in self.peers: return
            self.peers[key]={'id':key,'alias':label(info.get('alias','')),'ip':ip,'port':port,'fingerprint':fp,'code':security_code(fp),'seen':time.monotonic(),'manual':manual or self.peers.get(key,{}).get('manual',False)}

    def start_discovery(self):
        try:
            sock = socket.socket(socket.AF_INET,socket.SOCK_DGRAM,socket.IPPROTO_UDP)
            self.udp = sock
            sock.setsockopt(socket.SOL_SOCKET,socket.SO_REUSEADDR,1)
            if hasattr(socket,'SO_REUSEPORT'):
                try:sock.setsockopt(socket.SOL_SOCKET,socket.SO_REUSEPORT,1)
                except OSError:pass
            sock.bind(('',DISCOVERY_PORT))
            sock.settimeout(1)
            sock.setsockopt(socket.IPPROTO_IP,socket.IP_MULTICAST_TTL,1)
            interfaces=addresses() or ['0.0.0.0']
            joined=[]
            for ip in interfaces:
                try:
                    sock.setsockopt(socket.IPPROTO_IP,socket.IP_ADD_MEMBERSHIP,socket.inet_aton(GROUP)+socket.inet_aton(ip)); joined.append(ip)
                except OSError: pass
            if not joined: raise OSError('Multicast unavailable')
        except OSError:
            if self.udp: self.udp.close()
            self.udp=None
            self.warning='Nearby discovery is unavailable. Enter the receiver address manually.'
            return
        def broadcast(announce):
            for ip in joined:
                try:
                    sock.setsockopt(socket.IPPROTO_IP,socket.IP_MULTICAST_IF,socket.inet_aton(ip))
                    sock.sendto(json.dumps(self.info(announce)).encode(),(GROUP,DISCOVERY_PORT))
                except OSError: pass
        def discover():
            next_announce=0; last_response=0
            while not self.stopped.is_set():
                if time.monotonic()>next_announce: broadcast(True); next_announce=time.monotonic()+5
                try:
                    raw,(ip,_)=sock.recvfrom(4096)
                    info=json.loads(raw)
                    if not isinstance(info,dict) or not local_ip(ip) or info.get('fingerprint')==self.fingerprint: continue
                    self.add_peer(ip,info)
                    if info.get('announce') is True and time.monotonic()-last_response>1:
                        broadcast(False); last_response=time.monotonic()
                except (OSError,ValueError): continue
        threading.Thread(target=discover,daemon=True).start()

    def connection(self, ip, port, fingerprint=None, timeout=100):
        if not local_ip(ip): raise ValueError('Use a local IPv4 address.')
        # Trust is established by the displayed fingerprint, not by a public CA.
        context=ssl.SSLContext(ssl.PROTOCOL_TLS_CLIENT)
        context.check_hostname=False; context.verify_mode=ssl.CERT_NONE
        context.minimum_version=ssl.TLSVersion.TLSv1_2
        connection=http.client.HTTPSConnection(ip,port,context=context,timeout=timeout)
        try:
            connection.connect()
            actual=hashlib.sha256(connection.sock.getpeercert(binary_form=True)).hexdigest()
            if fingerprint and not secrets.compare_digest(actual,fingerprint): raise ValueError('Device security code changed. Rediscover it and compare codes again.')
            with self.lock:
                if self.stopped.is_set(): raise ValueError('Sharing stopped.')
                self.sockets.add(connection.sock)
                connection._nearby_socket=connection.sock
            return connection,actual
        except Exception: connection.close(); raise

    def close_connection(self, connection):
        with self.lock: self.sockets.discard(getattr(connection, '_nearby_socket', connection.sock))
        connection.close()

    def probe(self, address):
        match=re.fullmatch(r'([0-9.]+):([0-9]{1,5})',str(address).strip())
        if not match or not local_ip(match[1]) or not 1<=int(match[2])<=65535: raise ValueError('Enter the receiver IPv4 address and port shown on its screen.')
        conn,fp=self.connection(match[1],int(match[2]),timeout=4)
        try:
            conn.request('GET',PREFIX+'info')
            response=conn.getresponse()
            if response.status!=200: raise ValueError('Skill-Desk is not receiving at that address.')
            info=json.loads(response.read(16385))
            if not isinstance(info,dict) or info.get('skilldeskMode')!='receive': raise ValueError('Open Receive on the other device first.')
            info.update(fingerprint=fp,port=int(match[2]),protocol='https')
            self.add_peer(match[1],info,manual=True)
        finally: self.close_connection(conn)
        state = self.snapshot()
        state['selectedPeer'] = next((peer['id'] for peer in state['peers'] if peer['ip'] == match[1] and peer['port'] == int(match[2]) and peer['fingerprint'] == fp), None)
        return state

    def offer(self, handler, query):
        data=handler.body()
        with self.lock:
            if self.mode!='receive' or self.received is not None: handler.reply(409); return
            if self.pin_attempts>=10: handler.reply(429); return
            if not secrets.compare_digest(query.get('pin',''),self.pin):
                self.pin_attempts+=1; handler.reply(401); return
            if self.pending: handler.reply(409); return
            files=data.get('files')
            if not isinstance(files,dict) or len(files)!=1: handler.reply(400); return
            file_id,item=next(iter(files.items()))
            if not isinstance(file_id,str) or len(file_id)>100 or not isinstance(item,dict): handler.reply(400); return
            size,digest=item.get('size'),item.get('sha256')
            if type(size)!=int or not 0<size<=MAX_BYTES or not isinstance(digest,str) or not re.fullmatch('[a-f0-9]{64}',digest) or not str(item.get('fileName','')).endswith('.skilldesk.zip'):
                handler.reply(400); return
            info=data.get('info',{})
            if not isinstance(info,dict): handler.reply(400); return
            pending={'id':secrets.token_urlsafe(24),'token':secrets.token_urlsafe(32),'file':file_id,'size':size,'sha256':digest,
                     'ip':handler.client_address[0],'alias':label(info.get('alias','')),'event':threading.Event(),'decision':None,'deadline':0}
            self.pending=pending; self.phase='offered'; self.message='Accept or reject the incoming package.'
        approved=pending['event'].wait(90)
        with self.lock:
            if not approved or self.stopped.is_set() or pending['decision'] is not True or self.pending is not pending:
                if self.pending is pending: self.pending=None; self.phase='ready'; self.message='Transfer request declined or expired.'
                handler.reply(403); return
            pending['deadline']=time.monotonic()+120
            self.phase='receiving'; self.progress=0
        handler.reply(200,{'sessionId':pending['id'],'files':{file_id:pending['token']}})

    def decide(self, identifier, accept):
        with self.lock:
            pending=self.pending
            if not pending or pending['id']!=identifier or self.phase!='offered': raise ValueError('Transfer request expired.')
            pending['decision']=bool(accept); pending['event'].set()
        return self.snapshot()

    def upload(self, handler, query):
        with self.lock:
            p=self.pending
            if not p or self.phase!='receiving' or p['decision'] is not True or p['deadline']<time.monotonic() or p['ip']!=handler.client_address[0] or query.get('sessionId')!=p['id'] or query.get('fileId')!=p['file'] or not secrets.compare_digest(query.get('token',''),p['token']):
                handler.reply(403); return
            if handler.headers.get('Transfer-Encoding') or handler.headers.get('Content-Length')!=str(p['size']): handler.reply(400); return
            self.phase='transferring'
        content=bytearray()
        try:
            while len(content)<p['size']:
                if self.stopped.is_set() or self.pending is not p or time.monotonic()>p['deadline']: raise ValueError('Transfer cancelled or timed out.')
                chunk=handler.rfile.read(min(65536,p['size']-len(content)))
                if not chunk: raise ValueError('Transfer interrupted. No skills were installed.')
                content.extend(chunk)
                with self.lock: self.progress=round(len(content)*100/p['size'])
            if hashlib.sha256(content).hexdigest()!=p['sha256']: raise ValueError('Package checksum mismatch.')
            with self.lock:
                if self.stopped.is_set() or self.pending is not p: raise ValueError('Transfer cancelled.')
                self.received=bytes(content); self.pending=None; self.phase='received'; self.message='Package received. Review before installing.'
            handler.reply(200)
        except (OSError,ValueError) as error:
            with self.lock:
                if self.pending is p:
                    self.pending=None; self.phase='failed'; self.message=str(error)
            handler.reply(422)

    def send(self, peer_id, pin, confirmed, package):
        with self.lock:
            if self.mode!='send' or self.phase in {'sending','waiting'}: raise ValueError('A transfer is already running.')
            peer=self.peers.get(peer_id)
            if not peer or (not peer.get('manual') and time.monotonic()-peer['seen']>30): raise ValueError('Receiver is no longer nearby. Refresh or enter its address again.')
            if confirmed is not True or not re.fullmatch('[0-9]{6}',str(pin)): raise ValueError('Compare the security codes and enter the receiver PIN first.')
            self.phase='waiting'; self.progress=0; self.message='Waiting for the receiver to accept.'
        raw=base64.b64decode(package['data'])
        def transfer():
            conn=None
            try:
                conn,_=self.connection(peer['ip'],peer['port'],peer['fingerprint'])
                payload={'info':self.info(),'files':{'package':{'id':'package','fileName':'skills.skilldesk.zip','size':len(raw),'fileType':'application/zip','sha256':hashlib.sha256(raw).hexdigest()}}}
                conn.request('POST',PREFIX+'prepare-upload?'+urlencode({'pin':pin}),json.dumps(payload),{'Content-Type':'application/json'})
                response=conn.getresponse(); body=response.read(16385)
                if response.status!=200:
                    raise ValueError({401:'Receiver PIN is incorrect.',403:'Receiver declined or the request expired.',409:'Receiver is busy.',429:'Too many PIN attempts. Restart Receive.'}.get(response.status,'Receiver could not accept the package.'))
                result=json.loads(body); session=result['sessionId']; token=result['files']['package']
                if not isinstance(session,str) or not isinstance(token,str) or len(session)>200 or len(token)>200: raise ValueError('Invalid receiver response.')
                self.close_connection(conn)
                conn,_=self.connection(peer['ip'],peer['port'],peer['fingerprint'],timeout=15)
                route=PREFIX+'upload?'+urlencode({'sessionId':session,'fileId':'package','token':token})
                conn.putrequest('POST',route); conn.putheader('Content-Length',str(len(raw))); conn.putheader('Content-Type','application/octet-stream'); conn.endheaders()
                with self.lock: self.phase='sending'; self.message='Sending package…'
                deadline=time.monotonic()+120
                for offset in range(0,len(raw),65536):
                    if self.stopped.is_set() or time.monotonic()>deadline: raise ValueError('Transfer cancelled or timed out.')
                    conn.send(raw[offset:offset+65536])
                    with self.lock:self.progress=min(100,round((offset+65536)*100/len(raw)))
                response=conn.getresponse(); response.read(16385)
                if response.status!=200: raise ValueError('Receiver could not verify the transfer. Try again.')
                with self.lock: self.phase='sent'; self.message='Package sent. Review and install it on the receiving device.'
            except Exception as error:
                with self.lock: self.phase='failed'; self.message=str(error)
            finally:
                if conn:self.close_connection(conn)
        threading.Thread(target=transfer,daemon=True).start()
        return self.snapshot()


class Nearby:
    def __init__(self): self.session=None
    @property
    def active(self): return bool(self.session and not self.session.stopped.is_set())
    def start(self, mode):
        if self.active: raise ValueError('Close the current sharing session first.')
        self.session=Session(mode)
        return self.session.snapshot()
    def stop(self):
        if self.session:self.session.stop()
        self.session=None
        return {'active':False}
    def current(self):
        if not self.active: raise ValueError('Sharing expired. Open Send or Receive again.')
        return self.session
