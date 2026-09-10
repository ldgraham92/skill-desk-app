import os
from pathlib import Path
import sys
import tempfile
import unittest
from unittest.mock import patch
sys.path.insert(0, str(Path(__file__).resolve().parents[1]/'scripts'))
from skill_desk import Catalog, discovery_roots

class DiscoveryTests(unittest.TestCase):
    def test_default_catalog_reads_all_personal_libraries(self):
        with tempfile.TemporaryDirectory() as tmp, patch.dict(os.environ, {}, clear=True), patch('skill_desk.Path.home', side_effect=RuntimeError('No home available')):
            home = Path(tmp)
            for relative in ('.agents/skills', '.codex/skills', '.claude/skills'):
                folder = home/relative/'same-name'; folder.mkdir(parents=True)
                (folder/'SKILL.md').write_text('---\nname: same-name\ndescription: A test skill\n---\nInstructions.', encoding='utf-8')
            roots = discovery_roots(home)
            catalog = Catalog(roots[0], home/'cache.json', roots=roots)
            catalog.refresh(generate=False)
            self.assertEqual(len(catalog.rows), 3)
            self.assertEqual(len(catalog.files), 3)
            self.assertEqual(len(set(r['id'] for r in catalog.rows)), 3)
            self.assertTrue(any(r['prompt'].startswith('/') for r in catalog.rows))

    def test_environment_overrides_and_missing_libraries(self):
        with tempfile.TemporaryDirectory() as tmp:
            home=Path(tmp).resolve()
            with patch.dict(os.environ, {'CODEX_HOME':str(home/'custom-codex'), 'CLAUDE_CONFIG_DIR':str(home/'custom-claude')}, clear=True):
                roots=discovery_roots(home)
            self.assertIn(home/'custom-codex/skills', roots)
            self.assertIn(home/'custom-claude/skills', roots)
            roots[0].mkdir(parents=True)
            catalog=Catalog(roots[0],home/'cache.json',roots=roots)
            catalog.refresh(generate=False)
            self.assertEqual(catalog.errors, [])

    def test_linked_skills_are_not_duplicated(self):
        with tempfile.TemporaryDirectory() as tmp:
            home=Path(tmp).resolve(); first=home/'first'; second=home/'second'
            folder=first/'example';folder.mkdir(parents=True);second.mkdir()
            (folder/'SKILL.md').write_text('---\nname: example\ndescription: A test skill\n---\nInstructions.')
            (second/'example').symlink_to(folder,target_is_directory=True)
            catalog=Catalog(first,home/'cache.json',roots=[first,second])
            catalog.refresh(generate=False)
            self.assertEqual(len(catalog.rows),1)

    def test_availability_tracks_separate_same_named_copies(self):
        with tempfile.TemporaryDirectory() as tmp:
            home=Path(tmp).resolve(); roots=[home/'.codex/skills',home/'.claude/skills']
            for root in roots:
                folder=root/'example';folder.mkdir(parents=True)
                (folder/'SKILL.md').write_text('---\nname: example\ndescription: Test\n---\nInstructions.')
            catalog=Catalog(roots[0],home/'cache.json',roots=roots);catalog.refresh(generate=False)
            self.assertEqual(len(catalog.rows),2)
            self.assertTrue(all(row['installedHarnesses']==['claude','codex'] for row in catalog.rows))
            self.assertEqual(catalog.rows[0]['harnesses'],['codex'])
            self.assertEqual(catalog.rows[1]['harnesses'],['claude'])

    def test_cross_harness_preview_preserves_files_and_rechecks_conflicts(self):
        from management import Manager
        with tempfile.TemporaryDirectory() as tmp:
            home=Path(tmp).resolve();root=home/'.codex/skills';source=root/'example';source.mkdir(parents=True)
            (source/'SKILL.md').write_text('---\nname: example\ndescription: Test\n---\nRead [reference](reference.md).')
            (source/'reference.md').write_text('Preserve this reference.')
            target=home/'.claude/skills'
            manager=Manager(root,lambda *_:None,state=home/'state')
            draft=manager.stage([source],'Harness Copy','Test source',target_root=target,conflict_roots=[target])
            self.assertFalse(draft['candidates'][0]['conflict'])
            payload={'draft':draft['draft'],'candidate':'0'}
            manager.install(payload)
            self.assertEqual((target/'example/reference.md').read_text(),'Preserve this reference.')
            self.assertTrue((source/'SKILL.md').exists())
            with self.assertRaises(ValueError): manager.install(payload)
            self.assertEqual(manager.registry[str(target/'example')]['kind'],'Harness Copy')
            manager.temporary.cleanup()
