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
        with tempfile.TemporaryDirectory() as tmp, patch.dict(os.environ, {}, clear=True):
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
