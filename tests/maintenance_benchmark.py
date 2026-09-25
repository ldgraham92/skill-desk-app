"""Synthetic large-library and metadata-index measurements; no private history."""
import json,sys,tempfile,time,tracemalloc
from pathlib import Path
sys.path.insert(0,str(Path(__file__).resolve().parents[1]/'scripts'))
from library_tools import LibraryTools

with tempfile.TemporaryDirectory(prefix='skilldesk-benchmark-') as work:
 base=Path(work);entries=[]
 for i in range(1000):
  name=f'benchmark-{i:04d}';folder=base/name;folder.mkdir()
  (folder/'SKILL.md').write_text(f'---\nname: {name}\ndescription: Search this synthetic verification library.\n---\n'+('Review synthetic maintenance evidence.\n'*100)+('Unique search needle.' if i==500 else ''))
  entries.append(dict(id=name,name=name,folder=str(folder),harnesses=['codex'],project=''))
 library=LibraryTools(base/'state');tracemalloc.start();start=time.perf_counter();result=library.search(entries,dict(text='unique search needle'),{});elapsed=time.perf_counter()-start;current,peak=tracemalloc.get_traced_memory();tracemalloc.stop();assert len(result['results'])==1
 def manifest():return {str(p):(p.stat().st_size,p.stat().st_mtime_ns) for p in base.glob('*/SKILL.md')}
 start=time.perf_counter();first=manifest();first_time=time.perf_counter()-start
 start=time.perf_counter();second=manifest();second_time=time.perf_counter()-start;unchanged=sum(first[k]==v for k,v in second.items())
 path=Path(entries[500]['folder'])/'SKILL.md';path.write_text(path.read_text()+'\nA new synthetic instruction.')
 third=manifest();changed=sum(first.get(k)!=v for k,v in third.items());assert changed==1
 print(json.dumps(dict(skills=1000,searchSeconds=elapsed,searchBytes=result['bytesRead'],peakTracedBytes=peak,metadataIndex=dict(initialSeconds=first_time,repeatSeconds=second_time,unchanged=unchanged,changedAfterEdit=changed,storesPromptText=False,conclusion='A metadata-only index detects changed files but cannot reconstruct reviewed excerpts without reading their contents. No persistent prompt cache was introduced.')),indent=2))
