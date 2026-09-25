"""Independent full-read reference versus bounded sampling, using only generated data."""
import json
from pathlib import Path
import sys
import tempfile
import time
import tracemalloc
sys.path.insert(0,str(Path(__file__).resolve().parents[1]/'scripts'))
from usage_history import scan

def main():
 with tempfile.TemporaryDirectory(prefix='skilldesk-history-benchmark-') as work:
  root=Path(work);sessions=root/'sessions';sessions.mkdir();now=1800000000
  filler=json.dumps(dict(type='response_item',payload=dict(type='message',role='assistant',content='x'*2000)))+'\n'
  for i in range(48):
   with (sessions/f'{i:03}.jsonl').open('w') as file:
    file.write(json.dumps(dict(type='session_meta',payload=dict(cwd=f'/fixture/project-{i%8}')))+'\n')
    for step in range(4):
     file.write(json.dumps(dict(type='turn_context',payload=dict(cwd=f'/fixture/project-{i%8}')))+'\n')
     file.write(json.dumps(dict(type='event_msg',timestamp=now-i*3600-step,payload=dict(type='user_message',message=f'Synthetic session {i} step {step}: debug the sample database.')))+'\n')
     file.write(filler*450)
  # Deliberately independent: direct JSON records, no production parser helpers.
  expected=[]
  for path in sessions.glob('*.jsonl'):
   with path.open() as file:
    for line in file:
     row=json.loads(line)
     if row.get('type')=='event_msg' and row.get('payload',{}).get('type')=='user_message':expected.append(row['payload']['message'])
  results={}
  for deep in (False,True):
   tracemalloc.start();start=time.monotonic();sample=scan(['codex'],locations={'codex':root},now=now,deep=deep)
   elapsed=time.monotonic()-start;_,peak=tracemalloc.get_traced_memory();tracemalloc.stop()
   actual={r['text'] for r in sample['excerpts']}
   assert actual<=set(expected)
   assert sample['coverage']['codex']['bytesRead']<=sample['limits']['scanBytes']
   results['deep' if deep else 'standard']=dict(seconds=round(elapsed,3),peakBytes=peak,referencePrompts=len(expected),found=sample['found'],excerpts=len(actual),sessionsRepresented=sample['coverage']['codex']['sessionsIncluded'],sessionsScanned=sample['coverage']['codex']['sessionsScanned'],bytesRead=sample['coverage']['codex']['bytesRead'],partial=sample['partial'])
  print(json.dumps(results,indent=2))
if __name__=='__main__':main()
