"""Publish a complete tag release only after every platform build passes."""
import hashlib
import os
from pathlib import Path
import subprocess
root = Path(__file__).resolve().parent.parent
os.chdir(root)
tag = os.environ['RELEASE_TAG']
assets = sorted((root/'release-assets').iterdir())
for extension in ('.exe','.dmg','.deb'):
    if not any(p.suffix == extension for p in assets): raise RuntimeError(f'Missing {extension} installer')
checksums = root/'release-assets/SHA256SUMS.txt'
checksums.write_text(''.join(f'{hashlib.sha256(p.read_bytes()).hexdigest()}  {p.name}\n' for p in assets), encoding='utf-8')
assets.append(checksums)
notes = root/'docs/releases'/f'{tag}.md'
if not notes.exists(): raise RuntimeError(f'Add release notes at {notes.relative_to(root)}')
# Refuse to overwrite a published release or replace its installer bytes.
existing = subprocess.run(['gh','release','view',tag],capture_output=True)
if existing.returncode == 0: raise RuntimeError('Release already exists. Inspect it before retrying publication.')
preview = tag.startswith('v0.') or '-' in tag
command = ['gh','release','create',tag,'--verify-tag','--title',f'Skill-Desk {tag}', '--notes-file',str(notes)]
if preview: command.append('--prerelease')
subprocess.run(command+[str(p) for p in assets],check=True)
