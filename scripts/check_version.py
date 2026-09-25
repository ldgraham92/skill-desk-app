"""Keep release tags and package versions consistent."""
import json
import os
from pathlib import Path
import re
root = Path(__file__).resolve().parent.parent
version = json.loads((root/'package.json').read_text())['version']
package_lock = json.loads((root/'package-lock.json').read_text())
assert package_lock['version'] == version, 'npm lock version differs'
assert package_lock['packages']['']['version'] == version, 'npm root package version differs'
assert json.loads((root/'src-tauri/tauri.conf.json').read_text())['version'] == version
cargo_version = re.search(r'^version = "(.*?)"', (root/'src-tauri/Cargo.toml').read_text(), re.M).group(1)
assert cargo_version == version, 'Cargo version differs'
cargo_lock = (root/'src-tauri/Cargo.lock').read_text()
assert re.search(r'name = "skill-desk"\nversion = "([^"]+)"', cargo_lock).group(1) == version, 'Cargo lock version differs'
assert json.loads((root/'web/release.json').read_text())['version'] == version, 'What’s New version differs'
assert re.search(r"VERSION='([^']+)'", (root/'scripts/experience.py').read_text()).group(1) == version, 'Feedback version differs'
ref = os.environ.get('GITHUB_REF', '')
if ref.startswith('refs/tags/'):
    assert ref == 'refs/tags/v'+version, f'Tag does not match package version {version}'
print('Version:', version)
