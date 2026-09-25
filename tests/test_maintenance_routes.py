"""Maintenance coordination across registered projects, state and reviewed actions."""
import json
from pathlib import Path
import shutil
import sys
import tempfile
import time
import unittest
from unittest.mock import patch
from types import SimpleNamespace
sys.path.insert(0,str(Path(__file__).resolve().parents[1]/'scripts'))
import test_maintenance as foundation
from workbench_api import Workbench
from projects import Projects
from recommendations import Recommendations
from management import metadata
import threading

class FakeCatalog:
 def __init__(self,root):self.root=root;self.roots=[root];self.lock=threading.RLock();self.refresh()
 def refresh(self,generate=False):
  self.files={p.parent.name:str(p) for root in self.roots if root.exists() for p in root.glob('*/SKILL.md')}
 def snapshot(self):return dict(skills=[dict(id=key,name=metadata(Path(file).read_text())['name'],summary=metadata(Path(file).read_text())['description'],library=str(Path(file).parent.parent),harnesses=['codex']) for key,file in self.files.items()])

class RouteTests(unittest.TestCase):
 setUp=foundation.MaintenanceTests.setUp
 tearDown=foundation.MaintenanceTests.tearDown
 draft=foundation.MaintenanceTests.draft
 install=foundation.MaintenanceTests.install
 def workbench(self):
  self.catalog=FakeCatalog(self.root);self.projects=Projects(self.state);self.recs=Recommendations(self.base,None,experience=self.m.experience)
  return Workbench(self.m,self.catalog,self.projects,self.recs)
 def test_reconnect_retains_identity_notes_and_annotations(self):
  w=self.workbench();repo=self.base/'repo';repo.mkdir();(repo/'.git').mkdir();project=self.projects.add(dict(path=str(repo),name='Travel'));self.projects.notes(dict(id=project['id'],notes={'codex':'Retain this note'}));old=repo/'.agents/skills/example';w.library.annotate(old,dict(notes='Skill note'));self.m.registry[str(old)]=dict(kind='Existing');self.m.save();moved=self.base/'moved';repo.rename(moved)
  review=w.handle(dict(op='project-reconnect-preview',id=project['id'],path=str(moved)));w.handle(dict(op='project-reconnect',id=review['id']));result=self.projects.get(project['id']);self.assertEqual(result['notes']['codex'],'Retain this note');self.assertIn(str(moved.resolve()/'.agents/skills/example'),self.m.registry);self.assertIn(str(moved.resolve()/'.agents/skills/example'),w.library.data['skills'])
 @unittest.skipIf(sys.platform=='win32','Windows relocation is explicitly unavailable; tested below.')
 def test_library_relocation_keeps_discovery_and_replacement(self):
  folder=self.install();w=self.workbench();target=self.base/'relocated';review=w.handle(dict(op='relocate-preview',path=str(target)));w.handle(dict(op='relocate',id=review['id']));self.assertTrue(self.root.is_symlink());self.assertTrue((target/'example/SKILL.md').exists());d=self.draft();r=self.m.comparison(dict(draft=d['draft'],candidate='0'));self.m.replace(dict(draft=d['draft'],candidate='0',fingerprint=r['fingerprint']));self.assertTrue(folder.exists())
 @unittest.skipIf(sys.platform=='win32','Windows relocation is explicitly unavailable; tested below.')
 def test_relocation_rejects_late_edits(self):
  folder=self.install();w=self.workbench();review=w.handle(dict(op='relocate-preview',path=str(self.base/'relocated')));(folder/'notes.txt').write_text('late edit')
  with self.assertRaisesRegex(ValueError,'changed'):w.handle(dict(op='relocate',id=review['id']))
  self.assertFalse(self.root.is_symlink())
 def test_windows_relocation_is_rejected_without_changing_files(self):
  folder=self.install();w=self.workbench();target=self.base/'relocated'
  with patch('workbench_api.os',SimpleNamespace(name='nt')):
   with self.assertRaisesRegex(ValueError,'Windows directory-link'):
    w.handle(dict(op='relocate-preview',path=str(target)))
  self.assertFalse(target.exists());self.assertFalse(self.root.is_symlink())
  self.assertEqual((folder/'SKILL.md').read_text(),foundation.TEXT)
 def test_batch_results_and_favorites_share_preferences(self):
  self.install();w=self.workbench();r=w.handle(dict(op='batch',ids=['example'],action='favorite'));self.assertEqual(r['results'][0]['status'],'done');self.assertEqual(json.loads((self.state/'preferences.json').read_text())['saved'],['example']);review=w.handle(dict(op='batch-review',ids=['example']));r=w.handle(dict(op='batch',ids=['example'],action='archive',fingerprints={'example':review['items'][0]['fingerprint']}));self.assertEqual(r['results'][0]['status'],'done')
 def test_saved_search_keeps_all_filters(self):
  self.install();w=self.workbench();query=dict(text='instruction',agent='codex',project='some-project',origin='Repo Installed',tag='review',collection='Travel',modifiedAfter=123456,favorite=True);w.handle(dict(op='search-save',name='Travel changes',query=query));self.assertEqual(Workbench(self.m,self.catalog,self.projects,self.recs).library.data['searches']['Travel changes'],query)
 def test_saved_recommendation_freshness_and_covered_name(self):
  self.install();w=self.workbench();entry=w.entries()[0];existing=[dict(name=entry['name'],description=entry['summary'])];fingerprint=self.recs.context_digest(existing,None,'codex');self.m.experience.choose(dict(agent='codex',status='saved',contextDigest=fingerprint),dict(id='fixture:example',name='example',collection='fixture'));row=w.recommendation_choices()[0];self.assertTrue(row['satisfied']);self.assertIn('still match',row['freshness']);(self.root/'example/SKILL.md').write_text(foundation.TEXT.replace('local maintenance workflow','different verification workflow'));self.assertIn('changed',w.recommendation_choices()[0]['freshness'])
 def test_run_comparison_detects_evidence_change_without_disk_prompt_cache(self):
  w=self.workbench();request=dict(existing=[],target='codex');a=dict(summary='First',recommendations=[dict(id='fixture:skill',name='skill',reason='First reason',evidence=[dict(text='PRIVATE FIRST')])],target='codex',sampled=1);b=dict(a,summary='Second',recommendations=[dict(id='fixture:skill',name='skill',reason='Second reason',evidence=[dict(text='PRIVATE SECOND')])]);self.recs.finish(a,request);self.recs.finish(b,request);rows=self.recs.runs;result=w.handle(dict(op='recommendation-compare',left=rows[0]['id'],right=rows[1]['id']));self.assertTrue(result['changed'][0]['evidenceChanged']);self.assertFalse(any('PRIVATE' in p.read_text(errors='ignore') for p in self.state.rglob('*') if p.is_file()))
 def test_sample_save_requires_current_review_and_deletes_exact_sample(self):
  w=self.workbench();sample=dict(target='codex',scope='all',days=30,excerpts=[dict(id='prompt-1',source='codex',date='2026-09-24',text='Review the database migration.')]);self.recs.previews['review']=dict(sample=sample,expires=time.time()+900);result=w.handle(dict(op='sample-save',preview='review',provider='codex',excerpts=[dict(id='prompt-1',text='Redacted database review.')]));opened=w.handle(dict(op='sample-open',id=result['saved']));self.assertEqual(opened['excerpts'][0]['text'],'Redacted database review.');w.handle(dict(op='sample-delete',id=result['saved']));self.assertEqual(w.handle(dict(op='samples'))['samples'],[])
 def test_workspace_setting_restore_requires_restart(self):
  w=self.workbench();(self.state/'preferences.json').write_text(json.dumps(dict(theme='light')));data=w.handle(dict(op='backup-export',ids=[],settings=True));(self.state/'preferences.json').write_text(json.dumps(dict(theme='dark')));review=w.handle(dict(op='backup-preview',data=data['data']));r=w.handle(dict(op='backup-restore',id=review['id'],selections=[dict(index=0,replace=True)]));self.assertTrue(r['restartRequired']);self.assertTrue(self.m.restoreRestartRequired)
