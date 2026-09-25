import json
from contextlib import closing
import os
from pathlib import Path
import sqlite3
import sys
import tempfile
import threading
import time
import unittest
from unittest.mock import patch
from types import SimpleNamespace
sys.path.insert(0,str(Path(__file__).resolve().parents[1]/'scripts'))
from management import Manager
from usage_history import scan
from library_review import compare,health
from job_control import cancellation,Cancelled
from providers import AuthorProvider,generation_error,valid_model
import opencode_support

MD='---\nname: draft-example\ndescription: Use for reviewing a draft.\n---\nReview the sample.'
class WorkbenchTests(unittest.TestCase):
 def setUp(self):
  self.temp=tempfile.TemporaryDirectory();self.addCleanup(self.temp.cleanup);self.base=Path(self.temp.name)
  self.manager=Manager(self.base/'skills',lambda *_:{'skill_md':MD.replace('Review the sample.','Review the revised sample.')},self.base/'state');self.addCleanup(self.manager.temporary.cleanup)
 def draft(self):
  d=self.manager.prepare({'content':MD});return {'draft':d['draft'],'candidate':'0'}
 def test_edit_validation_does_not_write_and_stale_edit_is_rejected(self):
  d=self.draft();edit=dict(d,original=MD,content=MD.replace('sample','edited sample'))
  self.assertTrue(self.manager.edit_draft(edit,True)['valid'])
  self.assertEqual(self.manager.describe_draft(d['draft'])['candidates'][0]['content'],MD)
  self.manager.edit_draft(edit)
  with self.assertRaisesRegex(ValueError,'changed'):self.manager.edit_draft(edit)
  self.assertIn('edited sample',self.manager.revision(d)['diff'])
  self.assertEqual(self.manager.revision(d)['previous'],MD)
 def test_edit_missing_reference_preserves_original(self):
  d=self.draft()
  with self.assertRaisesRegex(ValueError,'reference'):self.manager.edit_draft(dict(d,original=MD,content=MD+'\n[missing](no-file.md)'))
  self.assertEqual(self.manager.revision(d)['current'],MD)
 def test_edit_invalid_metadata_and_installed_preview(self):
  d=self.draft()
  with self.assertRaises(ValueError):self.manager.edit_draft(dict(d,original=MD,content=MD.replace('draft-example','BAD NAME')))
  self.manager.install(d)
  with self.assertRaisesRegex(ValueError,'installed'):self.manager.edit_draft(dict(d,original=MD,content=MD+'More'))
 def test_revision_preserves_old_preview_and_supporting_files(self):
  d=self.draft();folder=self.manager.drafts[d['draft']]['paths']['0'];(folder/'notes.txt').write_text('Support')
  revised=self.manager.revise_draft(dict(d,instruction='Improve the steps'),lambda *_:None)
  self.assertNotEqual(d['draft'],revised['draft']);self.assertIn('revised',revised['candidates'][0]['content'])
  self.assertEqual(self.manager.revision(d)['current'],MD);self.assertIn('notes.txt',revised['candidates'][0]['files'])
 def test_revision_failure_keeps_original_and_removes_partial_preview(self):
  d=self.draft();self.manager.generate=lambda *_:{'skill_md':MD.replace('draft-example','wrong-name')}
  with self.assertRaisesRegex(ValueError,'name'):self.manager.revise_draft(dict(d,instruction='Improve'),lambda *_:None)
  self.assertEqual(list(self.manager.drafts),[d['draft']])
 def test_cancel_revision_preserves_original(self):
  d=self.draft();event=threading.Event()
  def generate(*_):event.set();return {'skill_md':MD}
  self.manager.generate=generate
  with cancellation(event),self.assertRaises(Cancelled):self.manager.revise_draft(dict(d,instruction='Improve'),lambda *_:None)
  self.assertEqual(list(self.manager.drafts),[d['draft']])
 def test_saved_draft_reopens_after_restart_and_deletes_only_saved_copy(self):
  d=self.draft();saved=self.manager.save_draft(d)
  other=Manager(self.manager.root,lambda *_:None,self.manager.state);self.addCleanup(other.temporary.cleanup)
  self.assertEqual(len(other.saved_drafts()),1)
  reopened=other.reopen_draft({'id':saved['saved']},{other.root})
  self.assertEqual(reopened['candidates'][0]['content'],MD)
  other.delete_saved_draft({'id':saved['saved']});self.assertEqual(other.saved_drafts(),[])
  self.assertEqual(other.describe_draft(reopened['draft'])['candidates'][0]['content'],MD)
 def test_saved_draft_unregistered_destination_and_traversal(self):
  saved=self.manager.save_draft(self.draft())
  with self.assertRaisesRegex(ValueError,'registered'):self.manager.reopen_draft({'id':saved['saved']},set())
  with self.assertRaises(ValueError):self.manager.delete_saved_draft({'id':'../archive'})
 def test_saved_revision_paths_are_checked_before_staging_or_reading(self):
  from experience import tree_digest
  saved=self.manager.save_draft(self.draft());base=self.manager.saved_path({'id':saved['saved']})
  record=json.loads((base/'record.json').read_text());before=set(self.manager.drafts)
  outside=self.base/'outside';outside.mkdir();(outside/'SKILL.md').write_text(MD)
  for index in (str(outside),'../../outside',-1,True,10):
   record['revisions']=[dict(index=index,digest=tree_digest(outside))]
   (base/'record.json').write_text(json.dumps(record))
   with self.subTest(index=index),patch('draft_tools.tree_digest',side_effect=AssertionError('Read an unchecked revision')):
    with self.assertRaisesRegex(ValueError,'revision'):self.manager.reopen_draft({'id':saved['saved']},{self.manager.root})
   self.assertEqual(set(self.manager.drafts),before)
  revisions=base/'revisions';revisions.mkdir();(revisions/'0').symlink_to(outside,target_is_directory=True)
  record['revisions']=[dict(index=0,digest=tree_digest(outside))];(base/'record.json').write_text(json.dumps(record))
  with self.assertRaisesRegex(ValueError,'revision'):self.manager.reopen_draft({'id':saved['saved']},{self.manager.root})
  self.assertEqual(set(self.manager.drafts),before)
 def test_file_preview_rejects_traversal_links_binary_and_large_content(self):
  d=self.draft();folder=self.manager.drafts[d['draft']]['paths']['0']
  (folder/'notes.txt').write_text('Readable support');(folder/'binary').write_bytes(b'\x00\xff')
  (folder/'large').write_bytes(b'x'*200001)
  self.assertEqual(self.manager.preview_file(dict(d,file='notes.txt'))['content'],'Readable support')
  for name in ('binary','large'):self.assertFalse(self.manager.preview_file(dict(d,file=name))['previewable'])
  with self.assertRaises(ValueError):self.manager.preview_file(dict(d,file='../record.json'))
  (folder/'linked').symlink_to(folder/'notes.txt')
  with self.assertRaises(ValueError):self.manager.preview_file(dict(d,file='linked'))
 def test_duplicate_does_not_modify_source_and_conflicts_remain_reviewable(self):
  d=self.draft();source=self.manager.drafts[d['draft']]['paths']['0'];(source/'support.txt').write_text('keep')
  duplicate=self.manager.duplicate_skill(source,{'name':'new-copy'},self.manager.root)
  self.assertEqual((source/'SKILL.md').read_text(),MD);self.assertIn('support.txt',duplicate['candidates'][0]['files'])
  self.manager.install({'draft':duplicate['draft'],'candidate':'0'})
  repeated=self.manager.duplicate_skill(source,{'name':'new-copy'},self.manager.root)
  self.assertTrue(repeated['candidates'][0]['conflict'])
 def test_comparison_detects_supporting_file_changes(self):
  a=self.manager.drafts[self.draft()['draft']]['paths']['0'];b=self.manager.drafts[self.draft()['draft']]['paths']['0']
  self.assertTrue(compare(a,b)['identical']);(b/'note.txt').write_text('additional')
  result=compare(a,b);self.assertFalse(result['identical']);self.assertEqual(result['added'],['note.txt'])
 def test_health_reports_invalid_metadata_and_unavailable_projects(self):
  folder=self.base/'invalid';folder.mkdir();(folder/'SKILL.md').write_text('missing metadata')
  result=health([dict(name='invalid',folder=folder)],[dict(name='gone',path='/missing',available=False)])
  self.assertEqual(len(result['issues']),2);self.assertEqual((folder/'SKILL.md').read_text(),'missing metadata')
 def test_opencode_event_errors_use_actionable_messages_without_provider_prose(self):
  for message,expected in [("OpenCode's free tier can only be used from within OpenCode PRIVATE",'free-tier'),('model not found PRIVATE','unavailable'),('free usage exceeded PRIVATE','usage limit')]:
   with self.assertRaises(RuntimeError) as error:opencode_support.text_result(json.dumps(dict(type='error',error=dict(message=message))))
   self.assertIn(expected,str(error.exception));self.assertNotIn('PRIVATE',str(error.exception))
 def test_opencode_fragments_and_unrelated_events(self):
  events=[{'type':'step_start'},{'type':'text','part':{'text':'{"ok":'}},{'type':'tool_use','part':{'text':'ignored'}},{'type':'text','part':{'text':'true}'}}]
  self.assertEqual(json.loads(opencode_support.text_result('\n'.join(map(json.dumps,events)))),{'ok':True})
 def test_model_listing_does_not_infer_prices_from_names(self):
  cli=self.base/'opencode';cli.write_text('fixture')
  with patch('opencode_support.capabilities',return_value={'standalone':True}),patch('opencode_support.run_process',return_value=SimpleNamespace(returncode=0,stdout='opencode/a-free\nopencode/a-free\nnot a model\nprovider/model#fast\n')) as run:
   result=opencode_support.models(str(cli));self.assertEqual(len(result['models']),2);self.assertIsNone(result['models'][0]['free']);self.assertIn('--standalone',run.call_args.args[0])
  self.assertTrue(valid_model('opencode','provider/model#fast'))
 def test_synthetic_connection_test_does_not_claim_success_for_bad_response(self):
  provider=AuthorProvider(self.base/'provider.json')
  with patch.object(provider,'generate',return_value={'ok':False}):
   with self.assertRaises(ValueError):provider.test_connection({'provider':'opencode','model':'opencode/free'},lambda *_:None)
  self.assertEqual(provider.connection_tests['opencode']['status'],'failed')
 def test_cancelled_scan_stops_before_reading(self):
  root=self.base/'history';root.mkdir();(root/'history.jsonl').write_text('{}')
  event=threading.Event();event.set()
  with cancellation(event),self.assertRaises(Cancelled):scan(['codex'],locations={'codex':root})
 def test_fair_scan_represents_many_sessions_and_registered_names(self):
  root=self.base/'codex';sessions=root/'sessions';sessions.mkdir(parents=True)
  now=1800000000;project=self.base/'repo';project.mkdir();(project/'.git').mkdir()
  for i in range(30):
   records=[dict(type='session_meta',payload={'cwd':str(project/'src')}),dict(type='event_msg',timestamp=now-i,payload={'type':'user_message','message':f'Request {i} to debug a synthetic database'})]+[dict(type='irrelevant',padding='x'*1000)]*200
   (sessions/f'{i}.jsonl').write_text('\n'.join(map(json.dumps,records)))
  with patch('usage_history.MAX_SCAN_BYTES',600000):sample=scan(['codex'],locations={'codex':root},now=now,registered_projects=[dict(path=str(project),name='Registered repository')])
  self.assertEqual(sample['coverage']['codex']['sessionsScanned'],30)
  self.assertEqual(sample['found'],30);self.assertTrue(all(r['project']=='Registered repository' for r in sample['excerpts']))
  self.assertEqual(sum(r['found'] for r in sample['breakdown']),30)
 def test_timezones_archives_and_cutoff(self):
  root=self.base/'codex';archive=root/'archived_sessions';archive.mkdir(parents=True)
  from usage_history import timestamp
  now=timestamp('2026-09-24T00:00:00Z')
  rows=[dict(type='event_msg',timestamp=date,payload={'type':'user_message','message':text}) for date,text in [('2026-09-24T02:00:00+02:00','At exactly current UTC time'),('2026-09-17T00:00:00Z','At exactly the cutoff time'),('2026-09-16T23:59:59Z','Too old for this sample'),('2026-09-24T00:06:00Z','Future time beyond allowance')]]
  (archive/'one.jsonl').write_text('\n'.join(map(json.dumps,rows)))
  sample=scan(['codex'],7,{'codex':root},now=now)
  self.assertEqual(sample['found'],2);self.assertEqual(sample['coverage']['codex']['sessionsFound'],1)
 def test_opencode_v2_reader_ignores_assistants_and_child_sessions(self):
  root=self.base/'opencode';root.mkdir();now=1800000000
  with closing(sqlite3.connect(root/'opencode.db')) as db, db:
   db.execute('create table session_v2 (id text,directory text,parent_id text)');db.execute('create table session_message (session_id text,type text,time_created integer,data text)')
   db.executemany('insert into session_v2 values (?,?,?)',[('root','/fixture',None),('child','/fixture','root')])
   for sid,role,text in [('root','user','Review the synthetic user prompt'),('root','assistant','PRIVATE assistant response'),('child','user','PRIVATE delegated prompt')]:
    db.execute('insert into session_message values (?,?,?,?)',(sid,role,now*1000,json.dumps(dict(text=text))))
  sample=scan(['opencode'],locations={'opencode':root},now=now)
  self.assertEqual(sample['found'],1);self.assertNotIn('PRIVATE',json.dumps(sample))

 def test_supporting_reference_warning_preserves_legitimate_cross_skill_template(self):
  from management import validate_folder
  d=self.draft();folder=self.manager.drafts[d['draft']]['paths']['0']
  (folder/'template.md').write_text('[Another skill](../another/SKILL.md)')
  result=validate_folder(folder);self.assertEqual(len(result['warnings']),1)
  self.assertIn('template.md',result['warnings'][0])
 def test_history_growth_during_read_marks_sample_partial(self):
  root=self.base/'codex';root.mkdir();file=root/'history.jsonl'
  file.write_text(json.dumps(dict(ts=1800000000,text='A synthetic history record.'))+'\n')
  real_open=Path.open;changed=[]
  def grow(path,*args,**kwargs):
   if path==file and args and args[0]=='rb' and not changed:
    changed.append(True)
    with real_open(path,'a') as output: output.write('{}\n')
   return real_open(path,*args,**kwargs)
  with patch('pathlib.Path.open',grow):sample=scan(['codex'],locations={'codex':root},now=1800000000)
  self.assertTrue(sample['partial']);self.assertEqual(sample['coverage']['codex']['changedFiles'],1)
  self.assertTrue(any('changed while' in n for n in sample['notes']))

if __name__=='__main__':unittest.main()
