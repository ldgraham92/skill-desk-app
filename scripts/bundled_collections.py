"""Read packaged collections without fetching or executing upstream code."""
import base64
import hashlib
import json


def catalog(project):
    return json.loads((project/'web/collections/catalog.json').read_text(encoding='utf-8'))


def package(project, collection_id):
    collection = next((c for c in catalog(project) if c['id'] == collection_id), None)
    if collection is None: raise ValueError('Unknown skill collection.')
    raw = (project/'web/collections'/collection['filename']).read_bytes()
    if hashlib.sha256(raw).hexdigest() != collection['sha256']:
        raise ValueError('Bundled collection checksum mismatch. Reinstall Skill-Desk.')
    return dict(data=base64.b64encode(raw).decode('ascii'), filename=collection['filename'], source=collection['name']+' · '+collection['url'])
