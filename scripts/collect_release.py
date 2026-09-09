"""Collect only redistributable installers from a successful platform build."""
from pathlib import Path
import shutil
root = Path(__file__).resolve().parent.parent
output = root/'release-assets'; output.mkdir(exist_ok=True)
files = []
for pattern in ('nsis/*-setup.exe','dmg/*.dmg','deb/*.deb'):
    files.extend((root/'src-tauri/target/release/bundle').glob(pattern))
if not files: raise RuntimeError('No installer was produced')
for file in files:
    shutil.copy2(file,output/file.name)
    print(file.name)
