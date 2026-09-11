from pathlib import Path
import json,sys,tempfile,time,unittest
from types import SimpleNamespace
from unittest.mock import patch
sys.path.insert(0,str(Path(__file__).resolve().parent.parent/'scripts'))
from experience import Experience,feedback_preview,tree_digest
from management import Manager
from projects import Projects
from readiness import check_agent

class ExperienceTests(unittest.TestCase):
 def setUp(self):
  self.temp=tempfile.TemporaryDirectory();self.addCleanup(self.temp.cleanup);self.root=Path(self.temp.name)
  self.manager=Manager(self.root/'skills',None,self.root/'state');self.addCleanup(self.manager.temporary.cleanup)
 def install(self):
  source=self.root/'source';source.mkdir(exist_ok=True);(source/'SKILL.md').write_text('---\nname: example\ndescription: Verify the result.\n---\nCheck the result.')
  preview=self.manager.stage([source],'Package Imported','Fixture collection');self.manager.install(dict(draft=preview['draft'],candidate='0'));self.manager.discard(dict(draft=preview['draft']))
  return self.manager.experience.history()[0]
 def test_history_rating_and_undo_survive_restart(self):
  row=self.install();self.assertEqual(row['name'],'example');self.assertEqual(row['source'],'Fixture collection')
  self.manager.experience.rate(dict(id=row['id'],rating='useful',note='Helped verify the result.'))
  self.assertEqual(Experience(self.root/'state').history()[0]['rating'],'useful')
  preview=self.manager.undo_preview(dict(id=row['id']));result=self.manager.undo_install(dict(preview=preview['preview']))
  self.assertFalse((self.root/'skills/example').exists());self.assertTrue((Path(result['backup'])/'SKILL.md').exists())
  self.assertEqual(Experience(self.root/'state').history()[0]['status'],'undone')
  with self.assertRaises(ValueError):self.manager.undo_preview(dict(id=row['id']))
 def test_old_installation_cannot_undo_a_new_copy(self):
  row=self.install();folder=self.root/'skills/example';import shutil;shutil.rmtree(folder)
  newer=self.install()
  self.assertNotEqual(row['id'],newer['id'])
  with self.assertRaisesRegex(ValueError,'current copy'):self.manager.undo_preview(dict(id=row['id']))
  self.assertTrue(folder.exists())
 def test_undo_rechecks_edits_after_preview(self):
  row=self.install();preview=self.manager.undo_preview(dict(id=row['id']));file=self.root/'skills/example/SKILL.md';file.write_text(file.read_text()+'\nA user edit.')
  with self.assertRaisesRegex(ValueError,'changed'):self.manager.undo_install(dict(preview=preview['preview']))
  self.assertIn('user edit',file.read_text());self.assertEqual(self.manager.experience.history()[0]['status'],'installed')
 def test_undo_rejects_links_and_expired_previews(self):
  row=self.install();preview=self.manager.undo_preview(dict(id=row['id']));self.manager.undo_previews[preview['preview']]['expires']=0
  with self.assertRaisesRegex(ValueError,'expired'):self.manager.undo_install(dict(preview=preview['preview']))
  target=self.root/'private';target.write_text('Keep this');(self.root/'skills/example/link').symlink_to(target)
  with self.assertRaisesRegex(ValueError,'links'):self.manager.undo_preview(dict(id=row['id']))
  self.assertEqual(target.read_text(),'Keep this')
 def test_choice_isolation_reset_and_persistence(self):
  store=self.manager.experience;skill=dict(id='ai-hero:example',name='example',collection='ai-hero')
  store.choose(dict(agent='codex',status='dismissed',note='Not for backend'),skill,'project-a')
  self.assertEqual(store.choices('claude','project-a'),[]);self.assertEqual(store.choices('codex','project-b'),[]);self.assertEqual(store.choices('codex',''),[])
  self.assertEqual(Experience(self.root/'state').choices('codex','project-a')[0]['note'],'Not for backend')
  store.choose(dict(agent='codex',status='saved',firstStep='$example Check it.'),skill,'project-a');self.assertEqual(len(store.choices('codex','project-a')),1)
  store.choose(dict(agent='codex',status='reset'),skill,'project-a');self.assertEqual(store.choices('codex','project-a'),[])
 def test_feedback_preview_is_bounded_and_only_contains_explicit_details(self):
  preview=feedback_preview(dict(kind='Bug',title='A control is confusing',message='I could not find the next step.',screen='Manage skills / For you'))
  self.assertIn('0.3.0',preview['body']);self.assertIn('I could not find',preview['body']);self.assertNotIn(str(Path.home()),preview['body'])
  with self.assertRaises(ValueError):feedback_preview(dict(kind='Bug',title='',message='Missing title'))
 def test_project_notes_stay_separate_and_persist(self):
  repo=self.root/'repo';repo.mkdir();(repo/'.git').mkdir();projects=Projects(self.root/'state');p=projects.add(dict(path=str(repo)))
  projects.notes(dict(id=p['id'],notes={'codex':'Backend tests','claude':'UI design'}))
  self.assertEqual(Projects(self.root/'state').get(p['id'])['notes'],{'codex':'Backend tests','claude':'UI design'})
  with self.assertRaises(ValueError):projects.notes(dict(id=p['id'],notes={'codex':'x'*2001}))

class ReadinessTests(unittest.TestCase):
 def run_fixture(self,name,authenticated=True):
  commands=[]
  def run(cmd,**kwargs):
   commands.append(cmd)
   if '--version' in cmd:return SimpleNamespace(returncode=0,stdout='2.1.268',stderr='')
   if '--help' in cmd:return SimpleNamespace(returncode=0,stdout='--ignore-user-config --ephemeral --output-schema --setting-sources --strict-mcp-config --disable-slash-commands --json-schema',stderr='')
   if name=='codex':return SimpleNamespace(returncode=0 if authenticated else 1,stdout='',stderr='Logged in using ChatGPT' if authenticated else 'Not logged in')
   return SimpleNamespace(returncode=0 if authenticated else 1,stdout=json.dumps({'loggedIn':authenticated,'email':'private@example.com'}),stderr='')
  with patch('readiness.executable',return_value='/fixture/'+name),patch('readiness.subprocess.run',side_effect=run):result=check_agent(name)
  self.assertNotIn('private@example.com',json.dumps(result));self.assertFalse(any('--print' in c or '-p' in c for c in commands));return result
 def test_saved_auth_without_inference(self):
  for name in ('codex','claude'):self.assertEqual(self.run_fixture(name)['status'],'ready');self.assertEqual(self.run_fixture(name,False)['status'],'sign-in')
 def test_missing_and_failure_are_actionable(self):
  with patch('readiness.executable',return_value=None):self.assertEqual(check_agent('claude')['status'],'missing')
  with patch('readiness.executable',return_value='/fixture/codex'),patch('readiness.subprocess.run',side_effect=OSError('PRIVATE DETAIL')):
   result=check_agent('codex');self.assertEqual(result['status'],'unknown');self.assertNotIn('PRIVATE',json.dumps(result))
