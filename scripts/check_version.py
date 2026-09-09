"""Keep release tags and package versions consistent."""
import json
import os
from pathlib import Path
import re
root = Path(__file__).resolve().parent.parent
version = json.loads((root/'package.json').read_text())['version']
assert json.loads((root/'src-tauri/tauri.conf.json').read_text())['version'] == version
cargo_version = re.search(r'^version = "(.*?)"', (root/'src-tauri/Cargo.toml').read_text(), re.M).group(1)
assert cargo_version == version, 'Cargo version differs'
ref = os.environ.get('GITHUB_REF', '')
if ref.startswith('refs/tags/'):
    assert ref == 'refs/tags/v'+version, f'Tag does not match package version {version}'
print('Version:', version)
