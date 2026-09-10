import base64
import io
import json
from pathlib import Path
import stat
import sys
import tempfile
import unittest
import zipfile

sys.path.insert(0, str(Path(__file__).resolve().parent.parent/'scripts'))
from management import Manager
from skill_packages import export_package, import_package


class PackageTests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.addCleanup(self.temp.cleanup)
        self.base = Path(self.temp.name)
        self.manager = Manager(self.base/'installed', None, self.base/'state')
        self.addCleanup(self.manager.temporary.cleanup)

    def skill(self, name):
        folder = self.base/'source'/name
        (folder/'references').mkdir(parents=True)
        (folder/'SKILL.md').write_text(f'---\nname: {name}\ndescription: A portable example\n---\nRead [details](references/guide.md).\n', encoding='utf-8')
        (folder/'references/guide.md').write_text('Example café notes', encoding='utf-8')
        (folder/'run.sh').write_text('#!/bin/sh\nexit 0\n')
        (folder/'run.sh').chmod(0o755)
        return folder

    def package(self, *folders):
        return export_package([dict(folder=f, harnesses=['codex']) for f in folders])

    def rewrite(self, package, mutate):
        source = zipfile.ZipFile(io.BytesIO(base64.b64decode(package['data'])))
        members = {i.filename: source.read(i) for i in source.infolist()}
        mutate(members)
        out = io.BytesIO()
        with zipfile.ZipFile(out, 'w') as z:
            for name, value in members.items(): z.writestr(name, value)
        return {'data': base64.b64encode(out.getvalue()).decode()}

    def test_round_trip_full_folders_and_conflict(self):
        folders = [self.skill('first-skill'), self.skill('second-skill')]
        package = self.package(*folders)
        self.assertNotIn(str(self.base), json.dumps(package['manifest']))
        preview = import_package(self.manager, package, self.manager.root, [self.manager.root])
        self.assertEqual(len(preview['candidates']), 2)
        for candidate, source in zip(preview['candidates'], folders):
            self.manager.install({'draft': preview['draft'], 'candidate': candidate['candidate']})
            for file in source.rglob('*'):
                if file.is_file(): self.assertEqual(file.read_bytes(), (self.manager.root/source.name/file.relative_to(source)).read_bytes())
        again = import_package(self.manager, package, self.manager.root, [self.manager.root])
        self.assertTrue(all(c['conflict'] for c in again['candidates']))
        with self.assertRaises(ValueError): self.manager.install({'draft': again['draft'], 'candidate': '0'})
        self.assertEqual(self.manager.listing()['installed'][0]['kind'], 'Package Imported')

    def test_reject_tampering_traversal_and_unlisted_files(self):
        package = self.package(self.skill('safe'))
        changes = [lambda m:m.update({'skills/0/SKILL.md':b'tampered'}), lambda m:m.update({'../outside':b'bad'}), lambda m:m.update({'extra.txt':b'bad'}), lambda m:m.update({'C:/outside':b'bad'}), lambda m:m.update({'skills/0/CON':b'bad'})]
        for change in changes:
            with self.subTest(change=change), self.assertRaises(ValueError): import_package(self.manager, self.rewrite(package, change))
        self.assertFalse(self.manager.root.exists())

    def test_reject_links_case_collisions_and_version(self):
        package = self.package(self.skill('safe'))
        out = io.BytesIO()
        with zipfile.ZipFile(out,'w') as z:
            info=zipfile.ZipInfo('link');info.external_attr=(stat.S_IFLNK|0o777)<<16
            z.writestr(info,'/private')
        with self.assertRaises(ValueError): import_package(self.manager,{'data':base64.b64encode(out.getvalue()).decode()})
        with self.assertRaises(ValueError): import_package(self.manager,self.rewrite(package,lambda m:m.update({'MANIFEST.JSON':m['manifest.json']})))
        def bad_version(m):
            manifest=json.loads(m['manifest.json']);manifest['version']=999;m['manifest.json']=json.dumps(manifest).encode()
        with self.assertRaises(ValueError): import_package(self.manager,self.rewrite(package,bad_version))

    def test_duplicate_names_flagged_and_export_credentials_rejected(self):
        folder=self.skill('safe')
        preview=import_package(self.manager,self.package(folder,folder))
        self.assertIn('Duplicate',preview['candidates'][1]['conflict'])
        (folder/'.env').write_text('SAMPLE=private')
        with self.assertRaises(ValueError): self.package(folder)

    def test_import_target_does_not_come_from_archive(self):
        folder=self.skill('safe')
        target=self.base/'other-provider'
        preview=import_package(self.manager,self.package(folder),target,[target])
        self.manager.install({'draft':preview['draft'],'candidate':'0'})
        self.assertTrue((target/'safe/SKILL.md').is_file())
        self.assertFalse(self.manager.root.exists())
