"""Collect installers plus signed updater bundles from the current platform."""
from pathlib import Path
import json
import platform
import shutil
import sys
root = Path(__file__).resolve().parent.parent
output = root/'release-assets'; output.mkdir(exist_ok=True)
bundle = root/'src-tauri/target/release/bundle'
version = json.loads((root/'package.json').read_text())['version']
files=[]
for pattern in ('nsis/*-setup.exe','dmg/*.dmg','deb/*.deb','appimage/*.AppImage'):
    files.extend(bundle.glob(pattern))
if not files: raise RuntimeError('No installer was produced')
for file in files: shutil.copy2(file,output/file.name)
arch='aarch64' if platform.machine().lower() in {'arm64','aarch64'} else 'x86_64'
pattern={'win32':'nsis/*-setup.exe.sig','darwin':'macos/*.app.tar.gz.sig','linux':'appimage/*.AppImage.sig'}[sys.platform]
for signature in bundle.glob(pattern):
    artifact=signature.with_suffix('')
    name=artifact.name
    if sys.platform=='darwin': name=f'Skill-Desk_{version}_{arch}.app.tar.gz'
    shutil.copy2(artifact,output/name)
    shutil.copy2(signature,output/(name+'.sig'))
    target={'win32':'windows','darwin':'darwin','linux':'linux'}[sys.platform]+'-'+arch
    (output/f'updater-{target}.json').write_text(json.dumps({target:{'signature':signature.read_text().strip(),'url':f'https://github.com/ldgraham92/skill-desk/releases/download/v{version}/{name}'}}))
print('Collected installer and available updater artifacts.')
