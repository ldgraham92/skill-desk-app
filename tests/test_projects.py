from pathlib import Path
import sys,tempfile,unittest
sys.path.insert(0,str(Path(__file__).resolve().parent.parent/'scripts'))
from projects import Projects,project_destination
from management import Manager

class ProjectTests(unittest.TestCase):
 def setUp(self):
  self.temp=tempfile.TemporaryDirectory();self.addCleanup(self.temp.cleanup);self.root=Path(self.temp.name)
  self.repo=self.root/'repo';self.repo.mkdir();(self.repo/'.git').mkdir();self.projects=Projects(self.root/'state')
 def test_onboarding_persists_without_modifying_repo_and_forgetting_preserves_files(self):
  before=list(self.repo.rglob('*'));p=self.projects.add(dict(path=str(self.repo),name='Portal'))
  self.assertEqual(list(self.repo.rglob('*')),before)
  self.assertEqual(Projects(self.root/'state').listing()[0]['id'],p['id'])
  self.assertEqual(self.projects.scope(self.repo/'.claude/skills'),p['id'])
  self.projects.remove(p['id']);self.assertTrue((self.repo/'.git').exists());self.assertEqual(self.projects.listing(),[])
 def test_invalid_duplicate_missing_and_linked_destinations(self):
  with self.assertRaises(ValueError):self.projects.add(dict(path=str(self.root)))
  p=self.projects.add(dict(path=str(self.repo)))
  with self.assertRaises(ValueError):self.projects.add(dict(path=str(self.repo/'.')))
  other=self.root/'outside';other.mkdir();(self.repo/'.claude').symlink_to(other,target_is_directory=True)
  with self.assertRaises(ValueError):project_destination(self.repo,'claude')
  (self.repo/'.claude').unlink();(self.repo/'.git').rmdir()
  self.assertFalse(self.projects.listing()[0]['available'])
  with self.assertRaises(ValueError):project_destination(self.repo,'codex')
 def test_project_installs_to_agent_path_and_rechecks_destination(self):
  manager=Manager(self.root/'personal',None,self.root/'state');self.addCleanup(manager.temporary.cleanup)
  folder=self.root/'source';folder.mkdir();(folder/'SKILL.md').write_text('---\nname: example\ndescription: Test project installs.\n---\nDo the work.')
  for agent in ['codex','claude']:
   destination=project_destination(self.repo,agent)
   draft=manager.stage([folder],'Package Imported','Fixture',destination,[destination]);manager.drafts[draft['draft']].update(project_path=str(self.repo),target_agent=agent)
   result=manager.install(dict(draft=draft['draft'],candidate='0'))
   self.assertTrue((destination/'example/SKILL.md').is_file());self.assertEqual(result['root'],str(destination))
   with self.assertRaises(ValueError):manager.install(dict(draft=draft['draft'],candidate='0'))
  folder2=self.root/'source2';folder2.mkdir();(folder2/'SKILL.md').write_text('---\nname: second\ndescription: Test a moved project.\n---\nDo the work.')
  draft=manager.stage([folder2],'Package Imported','Fixture',self.repo/'.agents/skills',[self.repo/'.agents/skills']);manager.drafts[draft['draft']].update(project_path=str(self.repo),target_agent='codex')
  (self.repo/'.git').rmdir()
  with self.assertRaisesRegex(ValueError,'unavailable'):manager.install(dict(draft=draft['draft'],candidate='0'))
  self.assertFalse((self.repo/'.agents/skills/second').exists())
