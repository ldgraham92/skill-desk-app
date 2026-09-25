"""Quit the packaged app helper during a fake agent job, then verify restart recovery."""
import json,os,queue,re,subprocess,sys,tempfile,threading,time,urllib.request,urllib.error
from pathlib import Path
import psutil
ROOT=Path(__file__).resolve().parents[1]
with tempfile.TemporaryDirectory(prefix='skilldesk-shutdown-') as tmp:
 base=Path(tmp);bin=base/'bin';bin.mkdir();marker=base/'started.json';root=base/'skills';root.mkdir();state=base/'state';state.mkdir()
 fake=bin/'codex';fake.write_text('#!'+sys.executable+'\nimport json,os,subprocess,sys,time\nfrom pathlib import Path\nif "--version" in sys.argv:print("synthetic");sys.exit()\nsys.stdin.read()\nchild=subprocess.Popen([sys.executable,"-c","import time;time.sleep(60)"])\nPath(os.environ["SKILL_DESK_TEST_MARKER"]).write_text(json.dumps([os.getpid(),child.pid]))\ntime.sleep(60)\n');fake.chmod(0o755)
 (state/'provider.json').write_text(json.dumps(dict(provider='codex',models={})))
 env=dict(os.environ,PATH=str(bin)+os.pathsep+os.environ['PATH'],SKILL_DESK_HOME=str(state),SKILL_DESK_TEST_MARKER=str(marker))
 def start():
  process=subprocess.Popen([str(ROOT/'dist/skilldesk-service'),'--desktop','--port','0','--no-author','--root',str(root)],env=env,stdin=subprocess.PIPE,stdout=subprocess.PIPE,stderr=subprocess.PIPE,text=True)
  lines=queue.Queue()
  def read():
   for line in process.stdout:lines.put(line)
  threading.Thread(target=read,daemon=True).start();url=None
  deadline=time.monotonic()+30
  while time.monotonic()<deadline:
   if process.poll() is not None:raise AssertionError('Packaged helper stopped')
   try:line=lines.get(timeout=.2)
   except queue.Empty:continue
   if line.startswith('Skill-Desk: '):url=line.split(': ',1)[1].strip();break
  assert url,'No helper URL'
  page=urllib.request.urlopen(url).read();token=json.loads(re.search(rb'window.skillDeskToken=(.*?);',page).group(1))
  def post(action,data):
   req=urllib.request.Request(url+'/api/'+action,data=json.dumps(data).encode(),headers={'Content-Type':'application/json','Origin':url,'X-Skill-Desk-Token':token})
   return json.loads(urllib.request.urlopen(req,timeout=10).read())
  return process,url,post
 process,url,post=start()
 try:
  job=post('create',dict(brief='Synthetic shutdown test.'))['job']
  for _ in range(100):
   if marker.exists():break
   time.sleep(.1)
  assert marker.exists(),'Fake agent never started'
  pids=json.loads(marker.read_text());children=[psutil.Process(pid) for pid in pids]
  try:post('create',dict(brief='Concurrent synthetic request'));raise AssertionError('Concurrent job accepted')
  except urllib.error.HTTPError as error:assert error.code==400
  process.stdin.write('q');process.stdin.flush();process.wait(timeout=10)
  _,alive=psutil.wait_procs(children,timeout=5);assert not alive,'Owned agent descendants survived desktop shutdown'
 finally:
  if process.poll() is None:process.kill();process.wait()
  process.stdin.close()
 second,url,post=start()
 try:
  status=json.loads(urllib.request.urlopen(url+'/api/jobs/'+job).read());assert status['status']=='failed' and status['phase']=='interrupted'
  overview=post('workbench',dict(op='overview'));assert len(overview['interrupted'])==1
  assert 'Synthetic shutdown test.' not in (state/'job-records.json').read_text()
  assert json.loads(marker.read_text())==pids,'Agent was retried after restart'
  print(json.dumps(dict(activeJobShutdown=True,concurrentJobRejected=True,ownedChildrenStopped=True,restartRecoveryVisible=True,promptPersisted=False,automaticRetry=False)))
 finally:
  second.stdin.write('q');second.stdin.flush();second.wait(timeout=10);second.stdin.close()
