import base64
import hashlib
import http.client
import json
from pathlib import Path
import socket
import ssl
import sys
import tempfile
import threading
import time
import unittest
from urllib.parse import urlencode

sys.path.insert(0,str(Path(__file__).resolve().parent.parent/'scripts'))
from nearby import Session, PREFIX, local_ip
from management import Manager
from skill_packages import export_package, import_package
from update_gate import UpdateGate


class NearbyTests(unittest.TestCase):
    def setUp(self):
        self.temp=tempfile.TemporaryDirectory();self.addCleanup(self.temp.cleanup)
        self.root=Path(self.temp.name)
        self.receiver=Session('receive',bind='127.0.0.1',port=0,discover=False)
        self.sender=Session('send',bind='127.0.0.1',port=0,discover=False)
        self.addCleanup(self.receiver.stop);self.addCleanup(self.sender.stop)
        folder=self.root/'example';folder.mkdir()
        (folder/'SKILL.md').write_text('---\nname: nearby-example\ndescription: Test nearby transfer\n---\nRead [notes](notes.md).\n',encoding='utf-8')
        (folder/'notes.md').write_text('Synthetic café notes.',encoding='utf-8')
        self.package=export_package([{'folder':folder,'harnesses':['codex']}])
        self.raw=base64.b64decode(self.package['data'])
        self.assertEqual(list(Path(self.receiver.temp.name).iterdir()), [])
        self.sender.probe(f'127.0.0.1:{self.receiver.port}')
        self.peer=next(iter(self.sender.peers))

    def wait(self, test, timeout=5):
        deadline=time.monotonic()+timeout
        while time.monotonic()<deadline:
            if test():return
            time.sleep(.02)
        self.fail('Timed out waiting for transfer state')

    def request(self, route, body=b'', method='POST'):
        conn,_=self.sender.connection('127.0.0.1',self.receiver.port,self.receiver.fingerprint,timeout=4)
        try:
            conn.request(method,route,body,{'Content-Type':'application/json'})
            response=conn.getresponse();return response.status,response.read()
        finally:self.sender.close_connection(conn)

    def offer_payload(self, digest=None, size=None):
        return json.dumps({'info':self.sender.info(),'files':{'package':{'fileName':'skills.skilldesk.zip','size':len(self.raw) if size is None else size,'sha256':digest or hashlib.sha256(self.raw).hexdigest()}}}).encode()

    def accepted_offer(self, digest=None):
        result=[]
        worker=threading.Thread(target=lambda:result.append(self.request(PREFIX+'prepare-upload?pin='+self.receiver.pin,self.offer_payload(digest))))
        worker.start()
        self.wait(lambda:self.receiver.phase=='offered')
        self.receiver.decide(self.receiver.pending['id'],True)
        worker.join(5);self.assertFalse(worker.is_alive())
        self.assertEqual(result[0][0],200)
        data=json.loads(result[0][1])
        return PREFIX+'upload?'+urlencode({'sessionId':data['sessionId'],'fileId':'package','token':data['files']['package']})

    def test_transfer_requires_acceptance_and_import_review(self):
        self.sender.send(self.peer,self.receiver.pin,True,self.package)
        self.wait(lambda:self.receiver.phase=='offered')
        self.assertIsNone(self.receiver.received)
        self.assertEqual(self.sender.phase,'waiting')
        self.receiver.decide(self.receiver.pending['id'],True)
        self.wait(lambda:self.sender.phase=='sent')
        self.assertEqual(self.receiver.received,self.raw)
        manager=Manager(self.root/'installed',None,self.root/'state');self.addCleanup(manager.temporary.cleanup)
        preview=import_package(manager,{'data':base64.b64encode(self.receiver.received).decode()},manager.root,[manager.root])
        self.assertFalse(manager.root.exists())
        manager.install({'draft':preview['draft'],'candidate':'0'})
        self.assertEqual((manager.root/'nearby-example/notes.md').read_text(encoding='utf-8'),'Synthetic café notes.')

    def test_rejection_transfers_no_package(self):
        self.sender.send(self.peer,self.receiver.pin,True,self.package)
        self.wait(lambda:self.receiver.phase=='offered')
        self.receiver.decide(self.receiver.pending['id'],False)
        self.wait(lambda:self.sender.phase=='failed')
        self.assertIsNone(self.receiver.received)
        self.assertIn('declined',self.sender.message)

    def test_pin_fingerprint_and_confirmation_are_required(self):
        with self.assertRaises(ValueError):self.sender.send(self.peer,self.receiver.pin,False,self.package)
        wrong='000000' if self.receiver.pin!='000000' else '111111'
        status,_=self.request(PREFIX+'prepare-upload?pin='+wrong,self.offer_payload())
        self.assertEqual(status,401);self.assertIsNone(self.receiver.pending)
        self.sender.peers[self.peer]['fingerprint']='0'*64
        self.sender.send(self.peer,self.receiver.pin,True,self.package)
        self.wait(lambda:self.sender.phase=='failed')
        self.assertIn('security code changed',self.sender.message)
        self.assertIsNone(self.receiver.pending)

    def test_lan_has_no_management_api_or_file_access(self):
        for path in ['/api/skills','/api/manage','/api/nearby-status','/instructions/nearby-example','/../../etc/passwd']:
            self.assertEqual(self.request(path,method='GET')[0],404)
        status,body=self.request(PREFIX+'info',method='GET')
        self.assertEqual(status,200)
        self.assertNotIn('pin',json.loads(body));self.assertNotIn('skills',json.loads(body))
        self.assertEqual(self.request(PREFIX+'upload?token=invalid',b'bad')[0],403)
        self.assertFalse(local_ip('8.8.8.8'))
        with self.assertRaises(ValueError):self.sender.probe('example.com:53317')

    def test_checksum_mismatch_and_token_reuse(self):
        route=self.accepted_offer('0'*64)
        self.assertEqual(self.request(route,self.raw)[0],422)
        self.assertIsNone(self.receiver.received)
        self.assertEqual(self.request(route,self.raw)[0],403)

    def test_interrupted_upload_is_discarded(self):
        route=self.accepted_offer()
        conn,_=self.sender.connection('127.0.0.1',self.receiver.port,self.receiver.fingerprint)
        conn.putrequest('POST',route);conn.putheader('Content-Length',str(len(self.raw)));conn.endheaders()
        conn.send(self.raw[:10])
        # Wait until headers arrive, then cut an upload that has actually begun.
        # An immediate Windows close can discard the request before it arrives.
        self.wait(lambda:self.receiver.phase=='transferring')
        conn.sock.shutdown(socket.SHUT_RDWR)
        self.sender.close_connection(conn)
        self.wait(lambda:self.receiver.phase=='failed')
        self.assertIsNone(self.receiver.received)
        self.assertIsNone(self.receiver.pending)

    def test_stop_closes_listener_and_cancels_pending_request(self):
        self.sender.send(self.peer,self.receiver.pin,True,self.package)
        self.wait(lambda:self.receiver.phase=='offered')
        port=self.receiver.port
        self.receiver.stop()
        self.wait(lambda:self.sender.phase=='failed')
        self.assertIsNone(self.receiver.received)
        with self.assertRaises(OSError):socket.create_connection(('127.0.0.1',port),timeout=.2)
        self.assertFalse(Path(self.receiver.temp.name).exists())

    def test_idle_expiry_and_update_gate(self):
        class Active:
            active=True
        manager=Manager(self.root/'installed',None,self.root/'state');self.addCleanup(manager.temporary.cleanup)
        manager.nearby=Active()
        self.assertFalse(UpdateGate().prepare(manager)['ready'])
        with self.receiver.lock:self.receiver.touched-=61
        self.wait(lambda:self.receiver.stopped.is_set())
