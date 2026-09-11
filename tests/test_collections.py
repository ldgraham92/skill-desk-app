import base64
import hashlib
import io
import json
from pathlib import Path
import sys
import tempfile
import unittest
import zipfile

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT/'scripts'))
import bundled_collections
from management import Manager
from skill_packages import import_package


class CollectionTests(unittest.TestCase):
    def test_every_bundled_skill_previews_installs_and_preserves_files(self):
        for collection in bundled_collections.catalog(ROOT):
            with self.subTest(collection=collection['id']), tempfile.TemporaryDirectory() as tmp:
                root = Path(tmp)
                manager = Manager(root/'installed', None, root/'state')
                self.addCleanup(manager.temporary.cleanup)
                package = bundled_collections.package(ROOT, collection['id'])
                result = import_package(manager, package, root/'installed', [root/'installed'])
                self.assertEqual(len(result['candidates']), collection['count'])
                self.assertEqual({s['name'] for s in collection['skills']}, {s['name'] for s in result['candidates']})
                with zipfile.ZipFile(io.BytesIO(base64.b64decode(package['data']))) as archive:
                    manifest = json.loads(archive.read('manifest.json'))
                for candidate, entry in zip(result['candidates'], manifest['skills']):
                    self.assertFalse(candidate['conflict'])
                    self.assertIn('SKILLDESK-UPSTREAM-LICENSE.txt', candidate['files'])
                    manager.install(dict(draft=result['draft'], candidate=candidate['candidate']))
                    for file, digest in entry['files'].items():
                        self.assertEqual(hashlib.sha256((root/'installed'/candidate['name']/file).read_bytes()).hexdigest(), digest)
                duplicate = import_package(manager, package, root/'installed', [root/'installed'])
                self.assertTrue(all(c['conflict'] for c in duplicate['candidates']))

    def test_unknown_collection_and_tampered_bundle_are_rejected(self):
        with self.assertRaisesRegex(ValueError, 'Unknown'):
            bundled_collections.package(ROOT, '../../anything')
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            folder = root/'web/collections'
            folder.mkdir(parents=True)
            collection = bundled_collections.catalog(ROOT)[0]
            (folder/'catalog.json').write_text(json.dumps([collection]))
            (folder/collection['filename']).write_bytes(b'tampered')
            with self.assertRaisesRegex(ValueError, 'checksum mismatch'):
                bundled_collections.package(root, collection['id'])
