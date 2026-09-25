"""Run browser QA with temporary libraries, fake agents, and guaranteed cleanup.

Set PLAYWRIGHT_MODULE to an installed Playwright module when it is not on NODE_PATH.
Screenshots and the JSON result go to the supplied evidence directory outside the repo.
"""
import os
from pathlib import Path
import signal
import socket
import subprocess
import sys
import tempfile
import time
import urllib.request
import psutil

ROOT=Path(__file__).resolve().parents[1]

def main():
    output=Path(sys.argv[1] if len(sys.argv)>1 else tempfile.mkdtemp(prefix='skilldesk-ui-evidence-')).resolve()
    if output.is_relative_to(ROOT):raise ValueError('Choose an evidence directory outside the repository.')
    output.mkdir(parents=True,exist_ok=True)
    with tempfile.TemporaryDirectory(prefix='skilldesk-browser-fixture-') as tmp:
        with socket.socket() as s:s.bind(('127.0.0.1',0));port=s.getsockname()[1]
        with (output/'server.log').open('w') as log:
            server=subprocess.Popen([sys.executable,str(ROOT/'tests/ui_fixture.py'),tmp,str(port)],stdout=log,stderr=log,start_new_session=os.name!='nt')
            try:
                deadline=time.monotonic()+15
                while time.monotonic()<deadline:
                    if server.poll() is not None:raise RuntimeError('QA fixture did not start. Check server.log.')
                    try:
                        urllib.request.urlopen(f'http://127.0.0.1:{port}/',timeout=1).close();break
                    except OSError:time.sleep(.1)
                else:raise RuntimeError('QA fixture startup timed out.')
                subprocess.run(['node',str(ROOT/'tests/browser_smoke.cjs'),f'http://127.0.0.1:{port}',tmp,str(output)],check=True,timeout=180)
            finally:
                # Agent jobs own separate process groups for cancellation. A
                # server-group signal alone would leave them behind on failure.
                try: descendants=psutil.Process(server.pid).children(recursive=True)
                except psutil.Error: descendants=[]
                if os.name=='nt':subprocess.run(['taskkill','/PID',str(server.pid),'/T','/F'],capture_output=True,timeout=8)
                else:
                    try:os.killpg(server.pid,signal.SIGTERM)
                    except ProcessLookupError:pass
                try:server.wait(timeout=5)
                except subprocess.TimeoutExpired:server.kill();server.wait(timeout=5)
                for child in reversed(descendants):
                    try: child.terminate()
                    except psutil.Error:pass
                _,alive=psutil.wait_procs(descendants,timeout=3)
                for child in alive:
                    try:child.kill()
                    except psutil.Error:pass
                psutil.wait_procs(alive,timeout=3)
    print('Temporary QA server and libraries removed. Evidence: '+str(output))

if __name__=='__main__':main()
