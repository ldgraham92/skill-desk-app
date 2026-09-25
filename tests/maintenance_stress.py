"""Bounded soak against disposable data; records memory, disk and process evidence."""
import gc,json,os,sys,tempfile,time
from pathlib import Path
import psutil
sys.path.insert(0,str(Path(__file__).resolve().parents[1]/'scripts'))
from management import Manager
from library_tools import LibraryTools
from usage_history import scan

seconds=int(sys.argv[1]) if len(sys.argv)>1 else 300
output=Path(sys.argv[2]) if len(sys.argv)>2 else Path('/tmp/skilldesk-maintenance-stress.json')
process=psutil.Process();samples=[];cycles=0;started=time.monotonic()
with tempfile.TemporaryDirectory(prefix='skilldesk-soak-') as work:
 base=Path(work);root=base/'library';root.mkdir();source=base/'source';source.mkdir();(source/'SKILL.md').write_text('---\nname: soak-example\ndescription: Verify durable maintenance with disposable synthetic content.\n---\nCheck the result.\n')
 for i in range(10):(source/f'notes-{i}.txt').write_text('Synthetic supporting content.\n'*300)
 manager=Manager(root,None,base/'state');library=LibraryTools(manager.state);initial=process.memory_info().rss
 while time.monotonic()-started<seconds:
  draft=manager.stage([source],'Markdown Imported','Synthetic soak')
  next=manager.file_changes(dict(draft=draft['draft'],candidate='0',expected=draft['candidates'][0]['treeDigest'],changes=[dict(action='edit',file='notes-0.txt',content='Revised synthetic supporting content.')]))
  if cycles%20==0:
   manager.install(dict(draft=next['draft'],candidate='0',reviewDigest=next['candidates'][0]['treeDigest']))
   installed=manager.listing()['installed'][0];manager.archive(installed)
   token=manager.listing()['archived'][-1]['token'];manager.restore(dict(token=token));manager.archive(manager.listing()['installed'][0])
  manager.discard(next);manager.discard(draft)
  assert not list(Path(manager.temporary.name).iterdir()),'Discarded previews leaked temporary files'
  library.annotate(root/'soak-example',dict(notes='Synthetic note',tags=['soak']))
  cycles+=1
  if cycles%10==0:
   gc.collect();samples.append(dict(cycle=cycles,seconds=round(time.monotonic()-started,2),rss=process.memory_info().rss,children=len(process.children(recursive=True)),temporaryDrafts=len(manager.drafts)))
  time.sleep(.1)
 manager.temporary.cleanup()
 retained=sum(p.stat().st_size for p in manager.state.rglob('*') if p.is_file())
 result=dict(seconds=round(time.monotonic()-started,2),cycles=cycles,initialRSS=initial,finalRSS=process.memory_info().rss,peakSampleRSS=max((x['rss'] for x in samples),default=initial),samples=samples,retainedRecoveryBytes=retained,children=len(process.children(recursive=True)))
 assert result['children']==0
 assert result['finalRSS']-initial<64_000_000,'Unexpected sustained RSS growth'
 output.write_text(json.dumps(result,indent=2))
 print(json.dumps({k:v for k,v in result.items() if k!='samples'}))
