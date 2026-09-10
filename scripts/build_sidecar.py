"""Build a self-contained service for the current OS/architecture."""
import os
from pathlib import Path
import shutil
import subprocess
import sys
ROOT = Path(__file__).resolve().parent.parent
os.chdir(ROOT)
triple = subprocess.check_output(['rustc', '--print', 'host-tuple'], text=True).strip()
subprocess.run([sys.executable, '-m', 'PyInstaller', '--noconfirm', '--clean', '--onefile', '--name', 'skilldesk-service', '--collect-submodules', 'watchdog', '--add-data', f'LICENSE{os.pathsep}.', '--add-data', f'licenses{os.pathsep}licenses', '--add-data', f'PSTACK-LICENSE.txt{os.pathsep}.', '--add-data', f'web{os.pathsep}web', '--add-data', f'marketing/index.html{os.pathsep}marketing', 'scripts/skill_desk.py'], check=True)
ext = '.exe' if sys.platform == 'win32' else ''
target = ROOT/'src-tauri/binaries'/f'skilldesk-service-{triple}{ext}'
target.parent.mkdir(parents=True, exist_ok=True)
shutil.copy2(ROOT/'dist'/f'skilldesk-service{ext}', target)
print(target)
