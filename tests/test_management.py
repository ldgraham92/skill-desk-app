import json
from pathlib import Path
import sys
import tempfile
import unittest
import threading
import time
sys.path.insert(0, str(Path(__file__).resolve().parents[1]/'scripts'))
from management import Manager, fingerprint

MD = '---\nname: isolated-test-skill\ndescription: Use for isolated lifecycle tests.\n---\n\n# Test\nRecord the requested result.\n'

class LifecycleTests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.base = Path(self.temp.name)
        self.root = self.base/'skills'; self.root.mkdir()
        self.manager = Manager(self.root, lambda p,s: {'skill_md': MD}, self.base/'state')
    def tearDown(self):
        self.manager.temporary.cleanup(); self.temp.cleanup()
    def install(self):
        draft = self.manager.prepare({'content': MD})
        return self.manager.install({'draft':draft['draft'],'candidate':'0'})
    def test_job_reports_generation_and_completion(self):
        entered, release = threading.Event(), threading.Event()
        def generate(prompt, schema):
            entered.set()
            self.assertTrue(release.wait(3))
            return {'skill_md': MD}
        self.manager.generate = generate
        token = self.manager.job('create', {'brief': 'Test progress'})['job']
        try:
            self.assertTrue(entered.wait(3))
            with self.manager.lock:
                job = dict(self.manager.jobs[token])
            self.assertEqual(job['status'], 'running')
            self.assertEqual(job['phase'], 'generating')
            self.assertEqual(job['action'], 'create')
            self.assertGreater(job['started_at'], 0)
        finally: release.set()
        deadline = time.time() + 3
        while self.manager.busy and time.time() < deadline: time.sleep(.01)
        job = self.manager.jobs[token]
        self.assertEqual(job['status'], 'complete')
        self.assertGreaterEqual(job['finished_at'], job['started_at'])
        self.assertEqual(list(self.root.iterdir()), [])

    def test_job_failure_has_terminal_status(self):
        def generate(prompt, schema): raise RuntimeError('Test generation failure')
        self.manager.generate = generate
        token = self.manager.job('create', {'brief': 'Test failure'})['job']
        deadline = time.time() + 3
        while self.manager.busy and time.time() < deadline: time.sleep(.01)
        job = self.manager.jobs[token]
        self.assertEqual(job['status'], 'failed')
        self.assertEqual(job['message'], 'Test generation failure')
        self.assertIn('finished_at', job)

    def test_install_conflict_archive_restore_origin(self):
        self.install(); folder = self.root/'isolated-test-skill'
        before = folder.joinpath('SKILL.md').read_bytes()
        with self.assertRaises(ValueError): self.install()
        self.assertEqual(before, folder.joinpath('SKILL.md').read_bytes())
        entry = self.manager.listing()['installed'][0]
        self.assertEqual(entry['kind'], 'Markdown Imported')
        self.manager.archive({'id':entry['id'],'fingerprint':entry['fingerprint']})
        self.assertFalse(folder.exists())
        archived = self.manager.listing()['archived'][0]
        self.manager.restore({'token':archived['token']})
        self.assertEqual(folder.joinpath('SKILL.md').read_bytes(), before)
        self.assertEqual(self.manager.listing()['installed'][0]['kind'], 'Markdown Imported')
        self.assertEqual(self.manager.listing()['archived'], [])
    def test_create_policy_and_registry_restart(self):
        draft = self.manager.create({'brief':'Make a test skill','explicit':True})
        self.assertEqual(draft['candidates'][0]['invocation'], 'Explicit request')
        self.manager.install({'draft':draft['draft'],'candidate':'0'})
        another = Manager(self.root, None, self.base/'state')
        self.assertEqual(another.listing()['installed'][0]['kind'],'User Created')
        another.temporary.cleanup()
    def test_plain_markdown_and_missing_reference(self):
        draft = self.manager.prepare({'content':'# Instructions\nWrite a result.','name':'plain-test','description':'Use for a test.'})
        self.assertEqual(draft['candidates'][0]['name'],'plain-test')
        with self.assertRaisesRegex(ValueError,'Missing'):
            self.manager.prepare({'content': MD+'[Instructions](references/absent.md)'})
    def test_documentation_examples_are_not_required_files(self):
        draft = self.manager.prepare({'content': MD+'\n```markdown\n[Example](FORMS.md)\n```\n'})
        self.assertEqual(draft['candidates'][0]['name'], 'isolated-test-skill')

    def test_stale_delete_and_traversal(self):
        self.install(); entry=self.manager.listing()['installed'][0]
        (self.root/entry['id']/'new.txt').write_text('New user work')
        with self.assertRaisesRegex(ValueError,'changed'): self.manager.archive(entry)
        with self.assertRaises(ValueError): self.manager.archive({'id':'../outside'})
        with self.assertRaises(ValueError): self.manager.prepare({'content':MD.replace('isolated-test-skill','../outside')})
    def test_full_folder_preserved_and_symlink_rejected(self):
        folder = self.base/'repo'; folder.mkdir(); (folder/'SKILL.md').write_text(MD)
        (folder/'scripts').mkdir(); (folder/'scripts/helper.sh').write_text('echo example')
        (folder/'LICENSE').write_text('license'); (folder/'agents').mkdir()
        (folder/'agents/openai.yaml').write_text('policy:\n  allow_implicit_invocation: false\n')
        draft=self.manager.stage([folder], 'Repo Installed','test@commit')
        self.manager.install({'draft':draft['draft'],'candidate':'0'})
        installed=self.root/'isolated-test-skill'
        self.assertEqual(fingerprint(installed),fingerprint(folder))
        (folder/'external').symlink_to(self.base, target_is_directory=True)
        with self.assertRaisesRegex(ValueError,'symbolic'): self.manager.stage([folder],'Repo Installed','test')
    def test_symlink_removal_preserves_target(self):
        target=self.base/'target'; target.mkdir(); (target/'SKILL.md').write_text(MD)
        (self.root/'linked-test').symlink_to(target, target_is_directory=True)
        entry=self.manager.listing()['installed'][0];self.manager.archive(entry)
        self.assertTrue((target/'SKILL.md').exists())
        self.assertFalse((self.root/'linked-test').exists())
        self.manager.restore(self.manager.listing()['archived'][0])
        self.assertTrue((self.root/'linked-test').is_symlink())

if __name__ == '__main__': unittest.main()
