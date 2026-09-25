"""Install 0.3.0 and upgrade it inside a disposable Windows CI runner."""
import hashlib
import json
import os
from pathlib import Path
import queue
import subprocess
import sys
import tempfile
import threading
import time
import urllib.request

ROOT = Path(__file__).resolve().parents[1]
OLD_SHA256 = 'd7b454772497d3685aab6e59b082bf6fd117b5ca0a04596aa852a9c4e43962d2'
# This immutable installer was also verified with the production updater public key.
OLD_URL = 'https://github.com/ldgraham92/skill-desk/releases/download/v0.3.0/Skill-Desk_0.3.0_x64-setup.exe'


def smoke_helper(app, root, state, version):
    env = dict(os.environ, SKILL_DESK_HOME=str(state), SKILL_DESK_NO_AUTHOR='1')
    process = subprocess.Popen([str(app/'skilldesk-service.exe'), '--desktop', '--port', '0',
                                '--no-author', '--root', str(root)], env=env,
                               stdin=subprocess.PIPE, stdout=subprocess.PIPE, stderr=subprocess.PIPE,
                               text=True, encoding='utf-8')
    lines = queue.Queue()
    def read():
        for line in process.stdout:
            lines.put(line)
    threading.Thread(target=read, daemon=True).start()
    try:
        for _ in range(60):
            if process.poll() is not None:
                raise AssertionError('Installed helper exited: '+process.stderr.read())
            try:
                line = lines.get(timeout=1)
            except queue.Empty:
                continue
            if line.startswith('Skill-Desk: '):
                url = line.split(': ', 1)[1].strip()
                break
        else:
            raise AssertionError('Installed helper did not start')
        def get(path):
            with urllib.request.urlopen(url+path, timeout=10) as response:
                return json.load(response)
        assert get('/api/release')['version'] == version
        assert get('/api/preferences')['saved'] == ['upgrade-example']
        assert any(s['name'] == 'upgrade-example' for s in get('/api/skills')['skills'])
    finally:
        if process.poll() is None:
            process.stdin.write('q'); process.stdin.flush()
            try:
                process.wait(timeout=15)
            except subprocess.TimeoutExpired:
                subprocess.run(['taskkill', '/PID', str(process.pid), '/T', '/F'],
                               capture_output=True, timeout=15, check=True)
                process.wait(timeout=10)
        for stream in (process.stdin, process.stdout, process.stderr):
            stream.close()


def main():
    if sys.platform != 'win32' or os.environ.get('GITHUB_ACTIONS') != 'true':
        raise RuntimeError('Run only inside a disposable Windows GitHub Actions runner.')
    version = json.loads((ROOT/'package.json').read_text(encoding='utf-8'))['version']
    installers = list((ROOT/'src-tauri/target/release/bundle/nsis').glob('*.exe'))
    assert len(installers) == 1, 'Expected one candidate NSIS installer'
    with tempfile.TemporaryDirectory(prefix='skilldesk-installed-upgrade-') as temporary:
        base = Path(temporary); app = base/'app'; root = base/'skills'; state = base/'state'
        skill = root/'upgrade-example'; skill.mkdir(parents=True); state.mkdir()
        instruction = skill/'SKILL.md'
        instruction.write_text('---\nname: upgrade-example\ndescription: Verify an isolated installer upgrade.\n---\nPreserve this skill.\n', encoding='utf-8')
        prefs = state/'preferences.json'; prefs.write_text(json.dumps(dict(saved=['upgrade-example'], theme='light', walkthrough=1, whatsNew='0.3.0')))
        preserved = {p: p.read_bytes() for p in (instruction, prefs)}
        old = base/'old-setup.exe'
        with urllib.request.urlopen(OLD_URL, timeout=90) as response:
            old.write_bytes(response.read(30_000_001))
        assert hashlib.sha256(old.read_bytes()).hexdigest() == OLD_SHA256
        try:
            subprocess.run([str(old), '/S', '/D='+str(app)], check=True, timeout=180)
            smoke_helper(app, root, state, '0.3.0')
            old_hash = hashlib.sha256((app/'Skill-Desk.exe').read_bytes()).hexdigest()
            # Use the updater plugin's NSIS update mode, preserving app data and shortcuts.
            subprocess.run([str(installers[0]), '/S', '/UPDATE', '/D='+str(app)], check=True, timeout=180)
            expected = ROOT/'src-tauri/target/release/Skill-Desk.exe'
            expected_hash = hashlib.sha256(expected.read_bytes()).hexdigest()
            # The installer launcher may return while a child finishes replacing files.
            deadline = time.monotonic()+60
            actual_hash = None
            while time.monotonic() < deadline:
                try:
                    actual_hash = hashlib.sha256((app/'Skill-Desk.exe').read_bytes()).hexdigest()
                except OSError:
                    pass
                if actual_hash == expected_hash:
                    break
                time.sleep(.5)
            assert actual_hash == expected_hash, json.dumps(dict(
                installer=installers[0].name, oldHash=old_hash,
                expectedHash=expected_hash, installedHash=actual_hash))
            smoke_helper(app, root, state, version)
            assert all(p.read_bytes() == value for p, value in preserved.items())
            print(json.dumps(dict(fromVersion='0.3.0', toVersion=version,
                                  nativeInstallerUpgrade=True, candidateBytesMatch=True,
                                  savedStatePreserved=True, installedHelperVerified=True)))
        finally:
            uninstaller = app/'uninstall.exe'
            if uninstaller.exists():
                subprocess.run([str(uninstaller), '/S', '_?='+str(app)], check=True, timeout=90)


if __name__ == '__main__':
    main()
