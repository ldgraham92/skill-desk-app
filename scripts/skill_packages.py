"""Portable skill archives. No machine paths, credentials or application state."""
import base64
import hashlib
import io
import json
from pathlib import Path, PurePosixPath
import re
import stat
import tempfile
import unicodedata
import zipfile

from management import inventory, validate_folder

MAX_BYTES = 100_000_000
MAX_FILES = 10000
MAX_SKILLS = 500


def portable_path(name):
    parts = name.split('/')
    if not name or len(name) > 240 or any(not p or p in {'.', '..'} or p.endswith((' ', '.')) or re.search(r'[\\:\x00-\x1f<>"|?*]', p) or re.fullmatch(r'(CON|PRN|AUX|NUL|COM[1-9]|LPT[1-9])(?:\..*)?', p, re.I) for p in parts):
        raise ValueError('Archive contains a path that is unsafe or not portable.')
    return PurePosixPath(name)


def export_package(entries):
    if not entries or len(entries) > MAX_SKILLS:
        raise ValueError('Select between 1 and 500 skills.')
    output = io.BytesIO()
    manifest = {'format': 'skilldesk-package', 'version': 1, 'skills': []}
    total = count = 0
    with zipfile.ZipFile(output, 'w', zipfile.ZIP_DEFLATED) as archive:
        for i, entry in enumerate(entries):
            folder = Path(entry['folder']).resolve()
            details = validate_folder(folder)
            files = {}
            for rel in inventory(folder):
                path = folder / rel
                name = path.relative_to(folder).as_posix()
                portable_path(f'skills/{i}/{name}')
                if path.is_symlink() or not path.resolve().is_relative_to(folder):
                    raise ValueError('Skill changed during export. Refresh and retry.')
                if any(p.lower() in {'.env', '.ssh', '.aws', '.credentials', 'credentials.json', 'auth.json'} or p.lower().startswith('.env.') for p in PurePosixPath(name).parts):
                    raise ValueError('Skill contains a credential/configuration file. Remove it from the skill before exporting: '+details['name'])
                data = path.read_bytes()
                total += len(data); count += 1
                if total > MAX_BYTES or count > MAX_FILES:
                    raise ValueError('Package exceeds 100 MB or 10,000 files. Export smaller groups.')
                files[name] = hashlib.sha256(data).hexdigest()
                info = zipfile.ZipInfo(f'skills/{i}/{name}')
                info.compress_type = zipfile.ZIP_DEFLATED
                info.external_attr = (stat.S_IFREG | (path.stat().st_mode & 0o777)) << 16
                archive.writestr(info, data)
            manifest['skills'].append({'name': details['name'], 'harnesses': entry.get('harnesses', []), 'files': files})
        manifest_bytes = json.dumps(manifest, ensure_ascii=False).encode('utf-8')
        if len(manifest_bytes) > 2_000_000: raise ValueError('Package file list is too large. Export fewer skills.')
        archive.writestr('manifest.json', manifest_bytes)
    data = output.getvalue()
    if len(data) > MAX_BYTES: raise ValueError('Compressed package exceeds 100 MB. Export fewer skills.')
    return {'filename': 'skills.skilldesk.zip', 'data': base64.b64encode(data).decode('ascii'), 'manifest': manifest, 'bytes': len(data)}


def import_package(manager, data, target_root=None, conflict_roots=None, selected_names=None):
    try:
        raw = base64.b64decode(data.get('data', ''), validate=True)
    except (ValueError, TypeError): raise ValueError('Invalid package encoding.')
    if not raw or len(raw) > MAX_BYTES: raise ValueError('Choose a Skill-Desk package up to 100 MB.')
    with tempfile.TemporaryDirectory(prefix='skilldesk-package-') as tmp, zipfile.ZipFile(io.BytesIO(raw)) as archive:
        infos = archive.infolist()
        if len(infos) > MAX_FILES + 1 or sum(x.file_size for x in infos) > MAX_BYTES + 2_000_000:
            raise ValueError('Expanded package exceeds its size or file limit.')
        names = set()
        for info in infos:
            portable_path(info.filename)
            key = unicodedata.normalize('NFC', info.filename).casefold()
            mode = info.external_attr >> 16
            if key in names or info.is_dir() or info.flag_bits & 1 or stat.S_IFMT(mode) not in {0, stat.S_IFREG}:
                raise ValueError('Package contains duplicate paths, links, directories or unsupported files.')
            names.add(key)
        if archive.getinfo('manifest.json').file_size > 2_000_000: raise ValueError('Package manifest is too large.')
        manifest = json.loads(archive.read('manifest.json'))
        if not isinstance(manifest, dict) or manifest.get('format') != 'skilldesk-package' or manifest.get('version') != 1:
            raise ValueError('Unsupported Skill-Desk package version.')
        entries = manifest.get('skills')
        if not isinstance(entries, list) or not 1 <= len(entries) <= MAX_SKILLS: raise ValueError('Invalid package skill count.')
        expected = {'manifest.json'}
        folders = []
        for i, entry in enumerate(entries):
            if not isinstance(entry, dict) or not isinstance(entry.get('files'), dict) or not entry['files']: raise ValueError('Invalid file manifest.')
            folder = Path(tmp)/str(i); folder.mkdir()
            for rel, digest in entry['files'].items():
                portable_path(rel)
                member = f'skills/{i}/{rel}'
                expected.add(member)
                content = archive.read(member)
                if hashlib.sha256(content).hexdigest() != digest: raise ValueError('Package checksum mismatch.')
                dest = folder.joinpath(*PurePosixPath(rel).parts)
                dest.parent.mkdir(parents=True, exist_ok=True)
                dest.write_bytes(content)
                dest.chmod(0o755 if (archive.getinfo(member).external_attr >> 16) & 0o111 else 0o644)
            if validate_folder(folder)['name'] != entry.get('name'): raise ValueError('Package skill name does not match its instructions.')
            folders.append(folder)
        if expected != {x.filename for x in infos}: raise ValueError('Package contains unlisted files.')
        if selected_names is not None:
            available = {entry['name'] for entry in entries}
            if not isinstance(selected_names, list) or not selected_names or not all(isinstance(n, str) and n in available for n in selected_names) or len(set(selected_names)) != len(selected_names):
                raise ValueError('Choose valid skills from this collection.')
            pairs = [(folder, entry) for folder, entry in zip(folders, entries) if entry['name'] in selected_names]
            folders, entries = map(list, zip(*pairs))
        result = manager.stage(folders, 'Package Imported', 'Imported Skill-Desk package', target_root=target_root, conflict_roots=conflict_roots)
        result['package'] = True
        seen = set()
        for candidate, entry in zip(result['candidates'], entries):
            candidate['harnesses'] = [h for h in entry.get('harnesses', []) if h in ('codex', 'claude')]
            if candidate['name'].casefold() in seen:
                candidate['conflict'] = 'Duplicate name in this package. Import copies separately into different providers.'
            seen.add(candidate['name'].casefold())
        return result
