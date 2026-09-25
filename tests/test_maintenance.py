"""Behavioral regressions for reviewed library maintenance."""
import base64
import io
import json
from pathlib import Path
import shutil
import sys
import tempfile
import threading
import unittest
from unittest.mock import patch
import zipfile
sys.path.insert(0,str(Path(__file__).resolve().parents[1]/'scripts'))
from durable_state import StateFile,atomic_json
from management import Manager
from experience import tree_digest
from library_tools import LibraryTools,quality
from upstream import merge_files
from workspace_backup import WorkspaceBackup

TEXT='---\nname: example\ndescription: Use this skill to verify a local maintenance workflow.\n---\nFirst line.\nMiddle line.\nLast line.\n'

class MaintenanceTests(unittest.TestCase):
 def setUp(self):
  self.temp=tempfile.TemporaryDirectory();self.base=Path(self.temp.name);self.root=self.base/'library';self.root.mkdir();self.state=self.base/'state';self.state.mkdir();self.m=Manager(self.root,None,self.state);self.source=self.base/'source';self.source.mkdir();(self.source/'SKILL.md').write_text(TEXT);(self.source/'notes.txt').write_text('old notes')
 def tearDown(self):self.m.temporary.cleanup();self.temp.cleanup()
 def draft(self):return self.m.stage([self.source],'Markdown Imported','test')
 def install(self):
  d=self.draft();self.m.install(dict(draft=d['draft'],candidate='0'));return self.root/'example'
 def test_stale_state_and_corruption_preserved(self):
  path=self.state/'record.json';atomic_json(path,{'old':1});a=StateFile(path,{});b=StateFile(path,{});a.save({'new':2})
  with self.assertRaisesRegex(ValueError,'another process'):b.save({})
  path.write_text('{broken');c=StateFile(path,{})
  with self.assertRaisesRegex(ValueError,'preserved'):c.save({})
  self.assertEqual(path.read_text(),'{broken')
 def test_whole_folder_edit_and_restore(self):
  d=self.draft();key=dict(draft=d['draft'],candidate='0',expected=d['candidates'][0]['treeDigest'])
  next=self.m.file_changes(dict(key,changes=[dict(action='edit',file='notes.txt',content='new notes')]))
  self.assertEqual((self.m.drafts[d['draft']]['paths']['0']/'notes.txt').read_text(),'old notes')
  newkey=dict(draft=next['draft'],candidate='0');revs=self.m.folder_revisions(newkey)
  restored=self.m.restore_revision(dict(newkey,index=0,expected=revs['current']))
  self.assertEqual((self.m.drafts[restored['draft']]['paths']['0']/'notes.txt').read_text(),'old notes')
 def test_supporting_revision_survives_restart(self):
  d=self.draft();next=self.m.file_changes(dict(draft=d['draft'],candidate='0',expected=d['candidates'][0]['treeDigest'],changes=[dict(action='edit',file='notes.txt',content='new')]))
  saved=self.m.save_draft(dict(draft=next['draft'],candidate='0',template=True));other=Manager(self.root,None,self.state)
  try:
   reopened=other.reopen_draft(dict(id=saved['saved']),{self.root});self.assertEqual(len(other.folder_revisions(dict(draft=reopened['draft'],candidate='0'))['revisions']),1);self.assertTrue(other.saved_drafts()[0]['template'])
  finally:other.temporary.cleanup()
 def test_file_reference_failure_preserves_original(self):
  (self.source/'SKILL.md').write_text(TEXT+'\n[Notes](notes.txt)');d=self.draft()
  with self.assertRaisesRegex(ValueError,'Missing'):self.m.file_changes(dict(draft=d['draft'],candidate='0',expected=d['candidates'][0]['treeDigest'],changes=[dict(action='rename',file='notes.txt',to='renamed.txt')]))
  self.assertTrue((self.m.drafts[d['draft']]['paths']['0']/'notes.txt').exists())
 def test_stale_file_editor_and_traversal_rejected(self):
  d=self.draft();key=dict(draft=d['draft'],candidate='0',expected='stale',changes=[dict(action='add',file='../escape',content='x')])
  with self.assertRaisesRegex(ValueError,'changed'):self.m.file_changes(key)
  key['expected']=d['candidates'][0]['treeDigest']
  with self.assertRaisesRegex(ValueError,'unsafe'):self.m.file_changes(key)
 def test_find_replace_reviews_all_text(self):
  (self.source/'notes.txt').write_text('First line.');d=self.draft();next=self.m.replace_text(dict(draft=d['draft'],candidate='0',expected=d['candidates'][0]['treeDigest'],find='First',replacement='Changed'))
  self.assertEqual(len(next['fileChanges']),2)
 def test_three_way_merges_nonoverlapping_edits(self):
  base={'a':b'one\ntwo\nthree\n'};local={'a':b'ONE\ntwo\nthree\n'};remote={'a':b'one\ntwo\nTHREE\n'}
  merged,conflicts,_,_=merge_files(base,local,remote);self.assertFalse(conflicts);self.assertEqual(merged['a'],b'ONE\ntwo\nTHREE\n')
 def test_deletion_conflicts_and_rename_review(self):
  merged,conflicts,changes,renames=merge_files({'a':b'old','b':b'rename'},{'a':b'local','b':b'rename'},{'c':b'rename'})
  self.assertEqual(conflicts[0]['file'],'a');self.assertTrue(conflicts[0]['upstreamDeleted']);self.assertEqual(renames,[dict(previous='b',current='c')]);self.assertEqual(merged['a'],b'local')
 def test_upstream_check_prepare_preserves_edits_and_baseline(self):
  d=self.draft();self.m.drafts[d['draft']]['upstream']={'0':dict(repo='https://github.com/example/repo',ref='',commit='old',path='skill')};self.m.install(dict(draft=d['draft'],candidate='0'));folder=self.root/'example';(folder/'notes.txt').write_text('local notes')
  def fake(repo,ref,dest,progress=None):
   shutil.copytree(self.source,dest/'skill');(dest/'skill'/'SKILL.md').write_text(TEXT+'Upstream addition.\n');return 'new'
  with patch('upstream.checkout',side_effect=fake):review=self.m.upstream.check(folder)
  next=self.m.upstream.prepare(dict(id=review['id']));comparison=self.m.comparison(dict(draft=next['draft'],candidate='0'));self.m.replace(dict(draft=next['draft'],candidate='0',fingerprint=comparison['fingerprint']))
  self.assertEqual((folder/'notes.txt').read_text(),'local notes');self.assertIn('Upstream addition',(folder/'SKILL.md').read_text());self.assertTrue(self.m.upstream.provenance(folder)['localChanges'])
 def test_source_change_during_install_cannot_publish(self):
  d=self.draft();real=shutil.copytree;folder=self.m.drafts[d['draft']]['paths']['0']
  def copying(src,dest,*a,**kw):
   result=real(src,dest,*a,**kw)
   if Path(dest)==self.root/'example':(folder/'notes.txt').write_text('changed during copy')
   return result
  with patch('management.shutil.copytree',side_effect=copying):
   with self.assertRaisesRegex(ValueError,'changed'):self.m.install(dict(draft=d['draft'],candidate='0'))
  self.assertFalse((self.root/'example').exists())
 def test_interrupted_operation_recovery_preserves_new_edits(self):
  dest=self.install();operation=self.m.transactions.begin('replace',dest,self.source);(dest/'notes.txt').write_text('new edit after crash');review=self.m.transactions.preview(operation['id']);self.assertTrue(review['diverged'])
  self.m.transactions.recover(operation['id'],review['current'],'before');self.assertEqual((dest/'notes.txt').read_text(),'old notes');copies=list((self.state/'transactions'/operation['id']).glob('displaced-*'));self.assertEqual((copies[0]/'notes.txt').read_text(),'new edit after crash')
 def test_recovery_stale_review_rejected(self):
  dest=self.install();op=self.m.transactions.begin('replace',dest,self.source);r=self.m.transactions.preview(op['id']);(dest/'notes.txt').write_text('late change')
  with self.assertRaisesRegex(ValueError,'after recovery review'):self.m.transactions.recover(op['id'],r['current'],'after')
 def test_backup_selection_checksums_and_restore(self):
  folder=self.install();backup=WorkspaceBackup(self.m);data=backup.export([dict(name='example',folder=folder)]);review=backup.preview(data,{self.root});(folder/'notes.txt').write_text('later')
  failed=backup.restore(dict(id=review['id'],selections=[dict(index=0,replace=True)]));self.assertEqual(failed['results'][0]['status'],'failed');self.assertEqual((folder/'notes.txt').read_text(),'later')
  review=backup.preview(data,{self.root});result=backup.restore(dict(id=review['id'],selections=[dict(index=0,replace=True)]));self.assertEqual(result['results'][0]['status'],'restored');self.assertEqual((folder/'notes.txt').read_text(),'old notes')
 def test_backup_tamper_and_destination_rejected(self):
  folder=self.install();backup=WorkspaceBackup(self.m);data=backup.export([dict(name='example',folder=folder)])
  with self.assertRaisesRegex(ValueError,'registered'):backup.preview(data,set())
  raw=io.BytesIO();old=zipfile.ZipFile(io.BytesIO(base64.b64decode(data['data'])))
  with zipfile.ZipFile(raw,'w') as new:
   for name in old.namelist():new.writestr(name,b'tampered' if name.endswith('notes.txt') else old.read(name))
  with self.assertRaisesRegex(ValueError,'checksum'):backup.preview(dict(data=base64.b64encode(raw.getvalue()).decode()),{self.root})
 def test_quality_portability_and_metadata_conflicts(self):
  (self.source/'SKILL.md').write_text(TEXT.replace('description: Use this skill to verify a local maintenance workflow.','description: Always use for everything.\ndisable-model-invocation: true')+'\nRun brew from /Users/example.\n');(self.source/'agents').mkdir();(self.source/'agents/openai.yaml').write_text('policy:\n  allow_implicit_invocation: true\n');codes={r['code'] for r in quality(self.source,['opencode'])['issues']};self.assertTrue({'broad-description','invocation-conflict','platform-specific','opencode-invocation'}<=codes)
 def test_search_organization_survives_content_change(self):
  folder=self.install();tools=LibraryTools(self.state);tools.annotate(folder,dict(tags=['travel'],collections=['Review'],notes='Private note',favorite=True));entries=[dict(id='example',folder=str(folder),name='example',harnesses=['codex'],project='')];self.assertEqual(len(tools.search(entries,dict(text='private',tag='travel'),{})['results']),1);(folder/'notes.txt').write_text('new');self.assertEqual(tools.data['skills'][str(folder)]['notes'],'Private note');self.assertEqual(tools.collection_coverage(entries)['collections'][0]['agents']['codex'],['example'])
 def test_duplicate_detection_ignores_location(self):
  second=self.base/'second';shutil.copytree(self.source,second);tools=LibraryTools(self.state);r=tools.duplicates([dict(name='example',folder=str(p)) for p in (self.source,second)]);self.assertEqual(len(r['exact']),1)
 def test_journal_does_not_persist_prompts(self):
  event=threading.Event();result=self.m.job('synthetic',dict(brief='PRIVATE PROMPT'),lambda d,p:event.wait(2));journal=(self.state/'job-records.json').read_text();self.assertNotIn('PRIVATE PROMPT',journal);other=Manager(self.root,None,self.state)
  try:self.assertEqual(len(other.interrupted_jobs),1)
  finally:other.temporary.cleanup();event.set()
  for _ in range(100):
   import time
   if self.m.jobs[result['job']]['status']!='running':break
   time.sleep(.01)
 def test_legacy_import_can_establish_exact_baseline(self):
  folder=self.install();commit='a'*40;self.m.registry[str(folder)]=dict(kind='Repo Installed',source='https://github.com/example/repo@'+commit+':skill');self.m.save();(folder/'notes.txt').write_text('local edit')
  def fake(repo,ref,destination,progress=None):
   self.assertEqual(ref,commit);shutil.copytree(self.source,destination/'skill');return commit
  with patch('upstream.checkout',side_effect=fake):result=self.m.upstream.bootstrap(folder)
  self.assertTrue(result['localChanges']);self.assertEqual(result['upstream']['commit'],commit);self.assertEqual((folder/'notes.txt').read_text(),'local edit')
  with self.assertRaisesRegex(ValueError,'full commit'):self.m.upstream.pin(folder,'main')
  self.assertEqual(self.m.upstream.pin(folder,'installed')['pin'],commit)
 def test_file_recovery_preserves_original_settings(self):
  destination=self.state/'preferences.json';destination.write_text('{"theme":"light"}');source=self.base/'new.json';source.write_text('{"theme":"dark"}');record=self.m.transactions.begin_file('restore-settings',destination,source);destination.write_bytes(source.read_bytes());review=self.m.transactions.preview(record['id']);self.m.transactions.recover(record['id'],review['current'],'before');self.assertEqual(json.loads(destination.read_text())['theme'],'light')
 def test_backup_staging_tamper_is_rejected(self):
  folder=self.install();backup=WorkspaceBackup(self.m);package=backup.export([dict(name='example',folder=folder)]);review=backup.preview(package,{self.root});staged=backup.previews[review['id']]['base']/'0/skill/notes.txt';staged.write_text('tampered after review');result=backup.restore(dict(id=review['id'],selections=[dict(index=0,replace=True)]));self.assertEqual(result['results'][0]['status'],'failed');self.assertEqual((folder/'notes.txt').read_text(),'old notes')
 def test_corrupt_origin_structure_is_preserved(self):
  path=self.state/'origins.json';path.write_text('{"example":"invalid record"}');other=Manager(self.root,None,self.state)
  try:
   self.assertTrue(other.registry_store.error)
   with self.assertRaisesRegex(ValueError,'preserved'):other.save()
   self.assertEqual(json.loads(path.read_text())['example'],'invalid record')
  finally:other.temporary.cleanup()
if __name__=='__main__':unittest.main()
