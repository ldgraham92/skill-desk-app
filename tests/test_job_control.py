"""Real subprocess cancellation tests never invoke an agent or network."""
import os
from pathlib import Path
import subprocess
import sys
import tempfile
import threading
import time
import unittest
sys.path.insert(0,str(Path(__file__).resolve().parents[1]/'scripts'))
from job_control import cancellation, run_process, Cancelled
from management import Manager

class JobTests(unittest.TestCase):
    def test_input_survives_polling_and_timeout_stops_process(self):
        event=threading.Event()
        with cancellation(event):
            result=run_process([sys.executable,'-c','import sys,time; text=sys.stdin.read(); time.sleep(.3); print(text)'],input='private draft',capture_output=True,text=True,timeout=3)
            self.assertEqual(result.stdout.strip(),'private draft')
            with self.assertRaises(subprocess.TimeoutExpired):
                run_process([sys.executable,'-c','import time; time.sleep(10)'],capture_output=True,timeout=.15)

    def test_large_input_reaches_a_slow_starting_process(self):
        with cancellation(threading.Event()):
            result=run_process([sys.executable,'-c','import sys,time; time.sleep(.4); print(len(sys.stdin.read()))'],input='x'*500000,capture_output=True,text=True,timeout=2)
        self.assertEqual(result.stdout.strip(),'500000')

    def test_cancel_job_stops_child_and_allows_next_job(self):
        with tempfile.TemporaryDirectory() as tmp:
            base=Path(tmp);manager=Manager(base/'skills',lambda *_:None,base/'state')
            self.addCleanup(manager.temporary.cleanup)
            started=threading.Event();pidfile=base/'pid'
            def task(data,progress):
                progress('generating','Testing cancellation');started.set()
                return run_process([sys.executable,'-c',f'import os,time; open({str(pidfile)!r},"w").write(str(os.getpid())); time.sleep(20)'],capture_output=True,timeout=30)
            token=manager.job('create',{},task)['job']
            self.assertTrue(started.wait(2))
            deadline=time.monotonic()+3
            while not pidfile.exists() and time.monotonic()<deadline:time.sleep(.01)
            self.assertTrue(pidfile.exists())
            manager.cancel_job({'job':token})
            while manager.busy and time.monotonic()<deadline:time.sleep(.01)
            self.assertEqual(manager.jobs[token]['status'],'cancelled')
            import psutil
            self.assertFalse(psutil.pid_exists(int(pidfile.read_text())))
            self.assertFalse(manager.busy)
            next_job=manager.job('import',{},lambda *_:{'ok':True})['job']
            while manager.busy and time.monotonic()<deadline:time.sleep(.01)
            self.assertEqual(manager.jobs[next_job]['status'],'complete')

    @unittest.skipIf(os.name=='nt','POSIX process group assertion; Windows needs a native run')
    def test_cancellation_stops_grandchild_process(self):
        import psutil
        with tempfile.TemporaryDirectory() as tmp:
            pidfile=Path(tmp)/'grandchild';event=threading.Event()
            def cancel_when_started():
                deadline=time.monotonic()+3
                while not pidfile.exists() and time.monotonic()<deadline:time.sleep(.01)
                event.set()
            watcher=threading.Thread(target=cancel_when_started);watcher.start()
            code=f'import subprocess,sys,time; child=subprocess.Popen([sys.executable,"-c","import time; time.sleep(30)"]); open({str(pidfile)!r},"w").write(str(child.pid)); time.sleep(30)'
            with cancellation(event),self.assertRaises(Cancelled):run_process([sys.executable,'-c',code],capture_output=True,timeout=5)
            watcher.join(3);self.assertTrue(pidfile.exists());pid=int(pidfile.read_text())
            try: self.assertEqual(psutil.Process(pid).status(),psutil.STATUS_ZOMBIE)
            except psutil.NoSuchProcess:pass

    def test_cancel_after_staging_discards_only_new_preview(self):
        with tempfile.TemporaryDirectory() as tmp:
            base=Path(tmp);manager=Manager(base/'skills',lambda *_:None,base/'state')
            self.addCleanup(manager.temporary.cleanup)
            staged=threading.Event();proceed=threading.Event()
            def task(data,progress):
                result=manager.prepare({'content':'---\nname: cancel-test\ndescription: For cancellation testing.\n---\nTest carefully.'})
                staged.set();proceed.wait(3);return result
            token=manager.job('import',{},task)['job'];self.assertTrue(staged.wait(2))
            manager.cancel_job({'job':token});proceed.set()
            deadline=time.monotonic()+3
            while manager.busy and time.monotonic()<deadline:time.sleep(.01)
            self.assertEqual(manager.jobs[token]['status'],'cancelled');self.assertEqual(manager.drafts,{})

    def test_install_retry_is_idempotent(self):
        with tempfile.TemporaryDirectory() as tmp:
            base=Path(tmp);manager=Manager(base/'skills',lambda *_:None,base/'state')
            self.addCleanup(manager.temporary.cleanup)
            draft=manager.prepare({'content':'---\nname: retry-test\ndescription: For retry testing.\n---\nTest carefully.'})
            data={'draft':draft['draft'],'candidate':'0'}
            manager.install(data);again=manager.install(data)
            self.assertTrue(again['alreadyInstalled'])
            self.assertEqual(len(manager.experience.history()),1)

if __name__=='__main__':unittest.main()
