"""Exercise the shipped Windows webviews without personal skills or CLI calls."""
import os
from pathlib import Path
import shutil
import subprocess
import sys
import tempfile

import psutil

ROOT = Path(__file__).resolve().parent.parent
if sys.platform != 'win32':
    raise SystemExit('This UI regression check requires Windows.')
with tempfile.TemporaryDirectory(prefix='skilldesk-updater-ui-') as folder:
    stage = Path(folder)
    shutil.copy2(ROOT/'src-tauri/target/release/Skill-Desk.exe', stage/'Skill-Desk.exe')
    shutil.copy2(ROOT/'src-tauri/binaries/skilldesk-service-x86_64-pc-windows-msvc.exe', stage/'skilldesk-service.exe')
    skills = stage/'skills'
    skills.mkdir()
    env = dict(os.environ, SKILL_DESK_NO_AUTHOR='1', SKILL_DESK_HOME=str(stage/'state'), SKILL_DESK_ROOT=str(skills))
    app = subprocess.Popen([str(stage/'Skill-Desk.exe')], env=env, stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
    try:
        # Keep automation out of the watchdog process: a blocked UIA call must time out.
        result = subprocess.run(['powershell.exe', '-NoProfile', '-ExecutionPolicy', 'Bypass', '-File',
                                 str(ROOT/'scripts/check_windows_updater.ps1'), '-AppPid', str(app.pid)],
                                timeout=110, capture_output=True)
        print(result.stdout.decode('utf-8', errors='replace'))
        if result.returncode:
            print(result.stderr.decode('utf-8', errors='replace'))
            raise SystemExit('Windows updater UI regression failed.')
    except subprocess.TimeoutExpired as error:
        print((error.stdout or b'').decode('utf-8', errors='replace'))
        raise SystemExit('Windows updater UI timed out, possible WebView2 callback deadlock.')
    finally:
        targets = []
        for process in psutil.process_iter(['exe']):
            try:
                if process.info['exe'] and Path(process.info['exe']).parent == stage:
                    targets.extend(process.children(recursive=True))
                    targets.append(process)
            except (psutil.NoSuchProcess, psutil.AccessDenied):
                pass
        for process in targets:
            try: process.kill()
            except (psutil.NoSuchProcess, psutil.AccessDenied): pass
        psutil.wait_procs(targets, timeout=10)
        app.wait(timeout=10)
