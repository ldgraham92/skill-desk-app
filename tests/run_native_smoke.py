"""Exercise an isolated debug app through its real macOS or Linux WebKit window."""
import json
import os
from pathlib import Path
import subprocess
import sys
import tempfile
import time
import psutil

ROOT=Path(__file__).resolve().parents[1]

def main():
 if sys.platform not in ('darwin','linux'):raise RuntimeError('This native interaction check requires macOS or Linux.')
 output=Path(sys.argv[1]).resolve();output.mkdir(parents=True,exist_ok=True)
 if output.is_relative_to(ROOT):raise ValueError('Store test evidence outside the repository.')
 app=ROOT/'src-tauri/target/debug/bundle/macos/Skill-Desk Test.app/Contents/MacOS/Skill-Desk'
 if sys.platform=='linux':
  images=list((ROOT/'src-tauri/target/debug/bundle/appimage').glob('*.AppImage'))
  if len(images)!=1:raise RuntimeError('Build exactly one isolated debug AppImage first.')
  app=images[0]
 if not app.is_file():raise RuntimeError('Build the debug test bundle first. See docs/LOCAL-TESTING.md.')
 report=output/'result.json'
 if report.exists():report.unlink()
 with tempfile.TemporaryDirectory(prefix='skilldesk-native-fixture-') as temporary:
  base=Path(temporary);root=base/'skills';root.mkdir();state=base/'state';state.mkdir()
  version=json.loads((ROOT/'package.json').read_text())['version']
  (state/'preferences.json').write_text(json.dumps(dict(walkthrough=1,whatsNew=version)))
  env=dict(os.environ,SKILL_DESK_TEST_MODE='1',SKILL_DESK_NO_AUTHOR='1',SKILL_DESK_ROOT=str(root),SKILL_DESK_HOME=str(state),SKILL_DESK_NATIVE_TEST_SCRIPT=str(ROOT/'tests/native_ui_smoke.js'),SKILL_DESK_NATIVE_TEST_REPORT=str(report))
  if sys.platform=='linux':
   # Exercise the bundled runtime without requiring FUSE mounts on the runner.
   subprocess.run([str(app),'--appimage-extract'],cwd=base,check=True,stdout=subprocess.DEVNULL,timeout=60)
   app=base/'squashfs-root/AppRun'
  with (output/'app.log').open('w') as log:
   process=subprocess.Popen([str(app)],env=env,stdout=log,stderr=log)
   try:
    deadline=time.monotonic()+120
    while not report.exists():
     if process.poll() is not None:raise RuntimeError('Native app exited before its report.')
     if time.monotonic()>deadline:raise RuntimeError('Native UI smoke timed out.')
     time.sleep(.2)
    result=json.loads(report.read_text());assert result['passed'],result
    assert (root/'native-review/notes.md').read_text()=='# Notes\nNative supporting file.'
    print(json.dumps(result))
   finally:
    try:children=psutil.Process(process.pid).children(recursive=True)
    except psutil.Error:children=[]
    process.terminate()
    try:process.wait(5)
    except subprocess.TimeoutExpired:process.kill();process.wait()
    for child in reversed(children):
     try:child.terminate()
     except psutil.Error:pass
    _,alive=psutil.wait_procs(children,timeout=3)
    for child in alive:
     try:child.kill()
     except psutil.Error:pass
    psutil.wait_procs(alive,timeout=3)
if __name__=='__main__':main()
