"""Transfer a synthetic package between two frozen services on this machine."""
import json
import os
from pathlib import Path
import queue
import re
import socket
import subprocess
import tempfile
import threading
import time
import urllib.request

ROOT=Path(__file__).resolve().parent.parent


class Instance:
    def __init__(self, base, skill=False):
        self.root=base/'skills';self.root.mkdir(parents=True)
        if skill:
            folder=self.root/'nearby-smoke';folder.mkdir()
            (folder/'SKILL.md').write_text('---\nname: nearby-smoke\ndescription: Synthetic nearby smoke check\n---\nRead [notes](notes.md).\n',encoding='utf-8')
            (folder/'notes.md').write_text('Sample café notes.',encoding='utf-8')
        binary=ROOT/'dist'/('skilldesk-service.exe' if os.name=='nt' else 'skilldesk-service')
        self.process=subprocess.Popen([str(binary),'--desktop','--port','0','--no-author','--root',str(self.root)],stdin=subprocess.PIPE,stdout=subprocess.PIPE,stderr=subprocess.PIPE,text=True,encoding='utf-8',env=dict(os.environ,SKILL_DESK_HOME=str(base/'state')))
        lines=queue.Queue()
        def output():
            for line in self.process.stdout:lines.put(line)
        threading.Thread(target=output,daemon=True).start()
        deadline=time.monotonic()+60
        try:
            while time.monotonic()<deadline:
                if self.process.poll() is not None:raise AssertionError('Frozen service did not start.')
                try:line=lines.get(timeout=.2)
                except queue.Empty:continue
                if line.startswith('Skill-Desk: '):self.url=line.split(': ',1)[1].strip();break
            else:raise AssertionError('Frozen service startup timed out.')
            page=urllib.request.urlopen(self.url,timeout=10).read()
            self.token=json.loads(re.search(rb'window.skillDeskToken=(.*?);',page).group(1))
        except Exception:self.close();raise

    def post(self, action, data=None):
        request=urllib.request.Request(self.url+'/api/'+action,data=json.dumps(data or {}).encode(),headers={'Content-Type':'application/json','Origin':self.url,'X-Skill-Desk-Token':self.token})
        with urllib.request.urlopen(request,timeout=15) as response:return json.load(response)

    def phase(self, expected):
        deadline=time.monotonic()+15
        while time.monotonic()<deadline:
            state=self.post('nearby-status')
            if state.get('phase')==expected:return state
            if state.get('phase')=='failed':raise AssertionError(state['message'])
            time.sleep(.1)
        raise AssertionError('Sharing did not reach '+expected)

    def close(self):
        if self.process.poll() is None:
            self.process.stdin.write('q');self.process.stdin.flush()
            try:self.process.wait(timeout=10)
            except subprocess.TimeoutExpired:self.process.kill();self.process.wait();raise AssertionError('Service did not quit.')
        self.process.stdin.close();self.process.stdout.close();self.process.stderr.close()


def main():
    with tempfile.TemporaryDirectory(prefix='skilldesk-nearby-smoke-') as tmp:
        instances=[]
        try:
            sender=Instance(Path(tmp)/'sender',skill=True);instances.append(sender)
            receiver=Instance(Path(tmp)/'receiver');instances.append(receiver)
            r=receiver.post('nearby-start',{'mode':'receive'})
            s=sender.post('nearby-start',{'mode':'send'})
            assert not receiver.post('update-prepare')['ready']
            peer=sender.post('nearby-probe',{'address':f"127.0.0.1:{r['port']}"})['peers'][0]
            assert peer['code']==r['code']
            exported=sender.post('package-export',{'ids':['nearby-smoke']})
            sender.post('nearby-send',{'peer':peer['id'],'pin':r['pin'],'confirmed':True,'export':exported['export']})
            offer=receiver.phase('offered')
            assert not list(receiver.root.iterdir()),'Skills installed before acceptance'
            receiver.post('nearby-decide',{'id':offer['incoming']['id'],'accept':True})
            receiver.phase('received');sender.phase('sent')
            assert not list(receiver.root.iterdir()),'Skills installed before import review'
            preview=receiver.post('nearby-preview',{'target':'shared'})
            assert not receiver.post('nearby-status')['active']
            receiver.post('install',{'draft':preview['draft'],'candidate':'0'})
            receiver.post('discard',{'draft':preview['draft']})
            assert (receiver.root/'nearby-smoke/notes.md').read_bytes()==(sender.root/'nearby-smoke/notes.md').read_bytes()
            sender.post('nearby-stop')
            for port in [s['port'],r['port']]:
                try:
                    sock=socket.create_connection(('127.0.0.1',port),timeout=.3);sock.close()
                    raise AssertionError('Sharing listener remained open')
                except OSError:pass
            print('Frozen services: TLS transfer, approval, import review, complete files and listener shutdown passed.')
        finally:
            for instance in reversed(instances):instance.close()

if __name__=='__main__':main()
