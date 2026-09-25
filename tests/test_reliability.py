import json
import os
from pathlib import Path
import shutil
import sys
import tempfile
import threading
import time
import unittest
from unittest.mock import patch
from types import SimpleNamespace
sys.path.insert(0,str(Path(__file__).resolve().parents[1]/'scripts'))
from management import Manager
from providers import AuthorProvider,executable,generation_error
from diagnostics import diagnostic_report
from readiness import check_agent
from usage_history import project_matches,scan

MD='---\nname: reliable-skill\ndescription: Test the recovery behavior.\n---\nVerify the result.'

class ReliabilityTests(unittest.TestCase):
 def setUp(self):
  patcher=patch('providers.opencode_support.capabilities',return_value={'standalone':True,'compatible':True});patcher.start();self.addCleanup(patcher.stop)
  self.tmp=tempfile.TemporaryDirectory();self.addCleanup(self.tmp.cleanup);self.root=Path(self.tmp.name)
  self.manager=Manager(self.root/'skills',lambda *_:{'skill_md':MD},self.root/'state');self.addCleanup(self.manager.temporary.cleanup)
 def install(self):
  draft=self.manager.prepare({'content':MD});self.manager.install(dict(draft=draft['draft'],candidate='0'));return self.manager.experience.history()[0]
 def test_job_request_retries_share_one_job_and_reject_changed_inputs(self):
  entered=threading.Event();release=threading.Event()
  def task(*_):entered.set();release.wait(2);return {'ok':True}
  payload={'requestId':'one-stable-request-1234','brief':'first'}
  job=self.manager.job('create',payload,task);self.assertTrue(entered.wait(1))
  try:
   self.assertEqual(job,self.manager.job('create',payload,task))
   with self.assertRaisesRegex(ValueError,'different inputs'):self.manager.job('create',dict(payload,brief='other'),task)
  finally:release.set()
  deadline=time.monotonic()+2
  while self.manager.busy and time.monotonic()<deadline:time.sleep(.01)
  self.assertEqual(job,self.manager.job('create',payload,task))
 def test_undo_preserves_moved_deleted_or_permission_changed_files(self):
  row=self.install();folder=self.root/'skills/reliable-skill'
  folder.rename(self.root/'moved')
  with self.assertRaisesRegex(ValueError,'missing'):self.manager.undo_preview({'id':row['id']})
  (self.root/'moved').rename(folder)
  file=folder/'SKILL.md';file.chmod(0o700)
  with self.assertRaisesRegex(ValueError,'changed'):self.manager.undo_preview({'id':row['id']})
  shutil.rmtree(folder)
  with self.assertRaisesRegex(ValueError,'missing'):self.manager.undo_preview({'id':row['id']})
 def test_undo_rejects_changed_root_symlink(self):
  actual=self.root/'first';actual.mkdir();link=self.root/'link';link.symlink_to(actual,target_is_directory=True)
  self.manager.root=link;row=self.install();link.unlink();second=self.root/'second';second.mkdir();link.symlink_to(second,target_is_directory=True)
  with self.assertRaisesRegex(ValueError,'location changed'):self.manager.undo_preview({'id':row['id']})
  self.assertTrue((actual/'reliable-skill/SKILL.md').exists())
 def test_unicode_spaces_worktree_and_missing_project_paths(self):
  repo=self.root/'café project';repo.mkdir();(repo/'.git').write_text('gitdir: /some/worktree')
  self.assertTrue(project_matches(str(repo/'src'),str(repo)))
  sibling=self.root/'café project-other';self.assertFalse(project_matches(str(sibling),str(repo)))
  alias=self.root/'alias';alias.symlink_to(repo,target_is_directory=True)
  self.assertTrue(project_matches(str(alias/'src'),str(repo)))
  self.assertFalse(project_matches('relative/path',str(repo)))
  self.assertFalse(project_matches('/repo','relative'))
 def test_diagnostics_allowlist_excludes_private_data(self):
  catalog=SimpleNamespace(lock=threading.RLock(),roots=[self.root],snapshot=lambda:{'skills':[{'name':'PRIVATE SKILL'}],'errors':['PRIVATE ERROR']})
  projects=SimpleNamespace(listing=lambda:[{'name':'PRIVATE PROJECT','path':'PRIVATE PATH','available':True}])
  provider=SimpleNamespace(name='codex',models={'codex':'PRIVATE MODEL'})
  self.manager.jobs['one']={'status':'failed','message':'PRIVATE OUTPUT','result':{'prompt':'PRIVATE PROMPT'}}
  with patch('diagnostics.executable',return_value='/PRIVATE/executable'):result=diagnostic_report(catalog,self.manager,projects,provider)
  self.assertNotIn('PRIVATE',json.dumps(result));self.assertEqual(result['jobs']['failed'],1)
 def test_missing_cli_from_gui_path_uses_known_user_bin(self):
  file=self.root/'.opencode/bin/opencode';file.parent.mkdir(parents=True);file.write_text('fixture');file.chmod(0o755)
  with patch('providers.Path.home',return_value=self.root),patch('providers.shutil.which',return_value=None):self.assertEqual(executable('opencode'),str(file))
 def test_provider_failures_do_not_echo_private_output(self):
  for output,message in [('401 PRIVATE','sign-in'),('rate limit PRIVATE','usage limit'),('unknown model PRIVATE','model is unavailable'),('unknown option PRIVATE','required option')]:
   result=generation_error('cursor',output);self.assertIn(message,result);self.assertNotIn('PRIVATE',result)
 def test_incompatible_cli_is_not_reported_ready(self):
  def run(cmd,**_):return SimpleNamespace(returncode=0,stdout='2.1.0' if '--version' in cmd else 'Logged in using ChatGPT',stderr='')
  with patch('readiness.executable',return_value='/fixture/codex'),patch('readiness.subprocess.run',side_effect=run):self.assertEqual(check_agent('codex')['status'],'update')
 def test_malformed_provider_envelopes_are_actionable(self):
  provider=AuthorProvider(self.root/'provider.json')
  for name in ('cursor','opencode','claude'):
   for output in ('not-json','[]','null','{}'):
    with self.subTest(name=name,output=output),patch('providers.executable',return_value='/fixture/'+name),patch('providers.subprocess.run',return_value=SimpleNamespace(returncode=0,stdout=output,stderr='PRIVATE')):
     with self.assertRaises(ValueError) as error:provider.generate('brief',{},provider=name)
     self.assertNotIn('PRIVATE',str(error.exception))
 def test_corrupt_settings_fall_back_to_installed_cli(self):
  settings=self.root/'provider.json'
  for data in ('[]','null','{"provider":[],"models":null}','{broken'):
   settings.write_text(data)
   with patch('providers.executable',side_effect=lambda name:'/fixture/claude' if name=='claude' else None):provider=AuthorProvider(settings)
   self.assertEqual(provider.name,'claude');self.assertEqual(provider.models,{})
 def test_history_unreadable_file_is_distinct_from_missing(self):
  root=self.root/'.codex';root.mkdir();file=root/'history.jsonl';file.write_text('{}')
  real_open=Path.open
  def denied(path,*args,**kwargs):
   if path==file:raise PermissionError('PRIVATE PATH')
   return real_open(path,*args,**kwargs)
  with patch('pathlib.Path.open',denied):sample=scan(['codex'],locations={'codex':root})
  self.assertEqual(sample['coverage']['codex']['unreadableFiles'],1);self.assertNotEqual(sample['coverage']['codex']['status'],'missing');self.assertNotIn('PRIVATE',json.dumps(sample));self.assertTrue(sample['partial'])

if __name__=='__main__':unittest.main()
