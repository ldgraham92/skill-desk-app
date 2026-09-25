"""Failure injection for copy, state, concurrency, and filesystem portability."""
import errno
import json
from pathlib import Path
import shutil
import sys
import tempfile
import threading
import unittest
from unittest.mock import patch
sys.path.insert(0,str(Path(__file__).resolve().parents[1]/'scripts'))
from management import Manager
from experience import tree_digest
from skill_packages import export_package
from upstream import checkout
from durable_state import atomic_json
from job_control import Cancelled,cancellation
import test_maintenance as foundation
TEXT=foundation.TEXT


class FailureTests(unittest.TestCase):
 setUp=foundation.MaintenanceTests.setUp
 tearDown=foundation.MaintenanceTests.tearDown
 draft=foundation.MaintenanceTests.draft
 install=foundation.MaintenanceTests.install
 def test_disk_full_during_install_preserves_recovery(self):
  d=self.draft();real=shutil.copytree
  def copy(src,dest,*args,**kwargs):
   if Path(dest)==self.root/'example':
    (Path(dest)/'partial.txt').write_text('partial')
    raise OSError(errno.ENOSPC,'Injected disk full')
   return real(src,dest,*args,**kwargs)
  with patch('management.shutil.copytree',side_effect=copy):
   with self.assertRaises(OSError):self.m.install(dict(draft=d['draft'],candidate='0'))
  self.assertFalse((self.root/'example').exists())
  record=self.m.transactions.records()[0];review=self.m.transactions.preview(record['id']);self.m.transactions.recover(record['id'],review['current'],'after');self.assertEqual((self.root/'example/SKILL.md').read_text(),TEXT)
 def test_permission_loss_preserves_installed_replacement(self):
  folder=self.install();d=self.draft();review=self.m.comparison(dict(draft=d['draft'],candidate='0'));old=tree_digest(folder)
  with patch('transactions.shutil.copytree',side_effect=PermissionError('Injected permission loss')):
   with self.assertRaises(PermissionError):self.m.replace(dict(draft=d['draft'],candidate='0',fingerprint=review['fingerprint']))
  self.assertEqual(tree_digest(folder),old)
 def test_registry_failure_rolls_back_install(self):
  d=self.draft()
  with patch.object(self.m.registry_store,'save',side_effect=OSError(errno.ENOSPC,'Injected registry disk full')):
   with self.assertRaises(OSError):self.m.install(dict(draft=d['draft'],candidate='0'))
  self.assertFalse((self.root/'example').exists())
 def test_concurrent_install_same_preview_is_idempotent(self):
  d=self.draft();barrier=threading.Barrier(2);results=[]
  def install():barrier.wait();results.append(self.m.install(dict(draft=d['draft'],candidate='0')))
  threads=[threading.Thread(target=install) for _ in range(2)]
  for t in threads:t.start()
  for t in threads:t.join()
  self.assertEqual(len(results),2);self.assertEqual(sum(bool(r.get('alreadyInstalled')) for r in results),1)
 def test_window_with_stale_preview_cannot_install_new_edit(self):
  d=self.draft();key=dict(draft=d['draft'],candidate='0');self.m.edit_draft(dict(key,original=TEXT,content=TEXT+'Changed elsewhere.'))
  with self.assertRaisesRegex(ValueError,'another window'):self.m.install(dict(key,reviewDigest=d['candidates'][0]['treeDigest']))
 def test_cancelled_copy_does_not_leave_draft(self):
  event=threading.Event();event.set()
  with cancellation(event):
   with self.assertRaises(Cancelled):self.draft()
  self.assertFalse(self.m.drafts)
 def test_offline_upstream_check_preserves_library(self):
  folder=self.install();before=tree_digest(folder)
  with patch('upstream.run_process',side_effect=OSError('Network unavailable')):
   with self.assertRaises(OSError):checkout('https://github.com/fixture/repo','main',self.base/'checkout')
  self.assertEqual(tree_digest(folder),before)
 def test_unicode_spaces_and_long_paths_round_trip(self):
  rel='references/Amsterdam café/日本語 '+('a'*120)+'.md';file=self.source/rel;file.parent.mkdir(parents=True);file.write_text('Unicode supporting notes')
  d=self.draft();package=self.m.export_draft(dict(draft=d['draft'],candidate='0'));self.assertGreater(package['bytes'],0)
 def test_reserved_windows_filename_blocks_export(self):
  (self.source/'CON.txt').write_text('not portable')
  with self.assertRaisesRegex(ValueError,'portable'):export_package([dict(folder=self.source)])
 def test_failed_atomic_state_write_preserves_old_bytes(self):
  path=self.state/'test.json';atomic_json(path,dict(value=1))
  with patch('durable_state.os.replace',side_effect=PermissionError('Injected write restriction')):
   with self.assertRaises(PermissionError):atomic_json(path,dict(value=2))
  self.assertEqual(json.loads(path.read_text()),dict(value=1));self.assertFalse(list(self.state.glob('.test.json-*')))
