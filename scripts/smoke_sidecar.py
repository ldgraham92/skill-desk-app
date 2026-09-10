"""Exercise the shipped executable with isolated state, no AI calls or real skills."""
import base64
import json
import os
from pathlib import Path
import queue
import re
import subprocess
import sys
import tempfile
import threading
import time
import urllib.request
import psutil
ROOT = Path(__file__).resolve().parent.parent

def main():
    binary = ROOT/'dist'/('skilldesk-service.exe' if sys.platform == 'win32' else 'skilldesk-service')
    with tempfile.TemporaryDirectory(prefix='skilldesk-smoke-') as tmp:
        root = Path(tmp)/'skills'; root.mkdir()
        env = dict(os.environ, SKILL_DESK_HOME=str(Path(tmp)/'state'))
        start = time.monotonic()
        process = subprocess.Popen([str(binary),'--desktop','--port','0','--no-author','--root',str(root)], stdin=subprocess.PIPE, stdout=subprocess.PIPE, stderr=subprocess.PIPE, text=True, encoding='utf-8', env=env)
        lines = queue.Queue()
        def read():
            for line in process.stdout: lines.put(line)
        threading.Thread(target=read, daemon=True).start()
        children = []
        try:
            url = None
            for _ in range(60):
                if process.poll() is not None: raise AssertionError(process.stderr.read())
                try: line = lines.get(timeout=1)
                except queue.Empty: continue
                if line.startswith('Skill-Desk: '): url=line.split(': ',1)[1].strip(); break
            assert url, 'Service did not start'
            ready_elapsed = time.monotonic()-start
            def get(path):
                with urllib.request.urlopen(url+path, timeout=5) as response: return response.read()
            page=get('/')
            assert b'/manage.js' in page
            token=json.loads(re.search(rb'window.skillDeskToken=(.*?);',page).group(1))
            request=urllib.request.Request(url+'/api/preferences', data=json.dumps({'saved':['smoke-test']}).encode(), headers={'Content-Type':'application/json','Origin':url,'X-Skill-Desk-Token':token})
            with urllib.request.urlopen(request,timeout=5) as response: assert response.status==200
            assert b'let saved=["smoke-test"]' in get('/')
            assert json.loads((Path(tmp)/'state/preferences.json').read_text())['saved']==['smoke-test']
            request=urllib.request.Request(url+'/api/preferences', data=json.dumps({'theme':'light'}).encode(), headers={'Content-Type':'application/json','Origin':url,'X-Skill-Desk-Token':token})
            urllib.request.urlopen(request, timeout=10).read()
            assert b'window.skillDeskTheme="light"' in get('/')
            preferences=json.loads((Path(tmp)/'state/preferences.json').read_text())
            assert preferences['saved']==['smoke-test'] and preferences['theme']=='light'

            assert json.loads(get('/api/skills'))['skills'] == []
            skill = root/'smoke-test'; skill.mkdir()
            (skill/'SKILL.md').write_text('---\nname: smoke-test\ndescription: Use to test packaging.\n---\nA caf\u00e9 test.', encoding='utf-8')
            for _ in range(50):
                snapshot=json.loads(get('/api/skills'))
                if snapshot['skills']: break
                time.sleep(.1)
            assert snapshot['skills'][0]['id']=='smoke-test', snapshot
            assert b'caf\xc3\xa9' in get('/instructions/smoke-test')
            assert b'author-provider' in get('/manage.js')
            def post(action, payload=None):
                request=urllib.request.Request(url+'/api/'+action,data=json.dumps(payload or {}).encode(),headers={'Content-Type':'application/json','Origin':url,'X-Skill-Desk-Token':token})
                with urllib.request.urlopen(request,timeout=5) as response:return json.load(response)
            exported = post('package-export', {'ids': ['smoke-test']})
            assert 'data' not in exported and exported['manifest']['skills'][0]['name']=='smoke-test'
            saved_package = Path(post('package-save', {'export': exported['export']})['path'])
            try: package_data = base64.b64encode(saved_package.read_bytes()).decode('ascii')
            finally: saved_package.unlink()
            preview = post('package-preview', {'data': package_data, 'target': 'shared'})
            assert preview['candidates'][0]['conflict']
            post('discard', {'draft': preview['draft']})
            skill.rename(Path(tmp)/'original-skill')
            preview = post('package-preview', {'data': package_data, 'target': 'shared'})
            assert not preview['candidates'][0]['conflict']
            post('install', {'draft': preview['draft'], 'candidate': '0'})
            post('discard', {'draft': preview['draft']})
            assert (skill/'SKILL.md').read_bytes()==(Path(tmp)/'original-skill/SKILL.md').read_bytes()
            assert json.loads(get('/api/manage'))['installed'][0]['kind']=='Package Imported'
            print('Shipped service package export, save, conflict check and import passed.')
            assert post('update-prepare')['ready'] is True
            blocked=urllib.request.Request(url+'/api/provider',data=b'{"provider":"codex"}',headers={'Content-Type':'application/json','Origin':url,'X-Skill-Desk-Token':token})
            try:
                urllib.request.urlopen(blocked,timeout=5)
                raise AssertionError('App update did not block new mutations')
            except urllib.error.HTTPError as error: assert error.code==400
            post('update-resume')

            children = psutil.Process(process.pid).children(recursive=True)
            print(f'Shipped service ready in {ready_elapsed:.2f}s; live file notification and UTF-8 passed.')
        finally:
            process.stdin.write('q'); process.stdin.flush()
            try: process.wait(timeout=10)
            except subprocess.TimeoutExpired: process.kill(); raise AssertionError('Service did not exit on the desktop quit signal')
        process.stdin.close()
        assert all(not c.is_running() for c in children), 'Orphaned service process'
        assert process.returncode == 0, process.returncode
        print('Desktop quit signal and child cleanup passed.')
if __name__ == '__main__': main()
