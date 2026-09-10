import sys,threading,unittest,tempfile,json
from pathlib import Path
from types import SimpleNamespace
sys.path.insert(0,str(Path(__file__).resolve().parents[1]/'scripts'))
from update_gate import UpdateGate
from publish_release import manifest
class UpdateTests(unittest.TestCase):
    def test_waits_for_jobs_and_drafts_and_blocks_new_generation(self):
        gate=UpdateGate();manager=SimpleNamespace(lock=threading.RLock(),busy=True,drafts={})
        self.assertFalse(gate.prepare(manager)['ready'])
        manager.busy=False;manager.drafts={'preview':{}}
        self.assertFalse(gate.prepare(manager)['ready'])
        manager.drafts={}
        gate.lock.acquire()
        self.assertFalse(gate.prepare(manager)['ready'])
        gate.lock.release()
        self.assertTrue(gate.prepare(manager)['ready'])
        with self.assertRaises(RuntimeError):gate.author(lambda:'called')
        gate.resume();self.assertEqual(gate.author(lambda:'called'),'called')
    def test_manifest_requires_every_signed_platform(self):
        with tempfile.TemporaryDirectory() as tmp:
            folder=Path(tmp)
            with self.assertRaises(RuntimeError):manifest(folder,'v0.2.0','notes')
            for target in ['windows-x86_64','darwin-aarch64','linux-x86_64']:
                (folder/f'updater-{target}.json').write_text(json.dumps({target:{'signature':'test-signature','url':'https://github.com/ldgraham92/skill-desk/releases/download/v0.2.0/artifact'}}))
            self.assertEqual(len(manifest(folder,'v0.2.0','notes')['platforms']),3)
            with self.assertRaises(RuntimeError):manifest(folder,'v0.2.1','notes')
