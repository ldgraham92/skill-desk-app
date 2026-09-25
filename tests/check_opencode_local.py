"""Optional integration checks against an installed OpenCode V2 CLI.

Modes: normal, denied, inherited, slow. Uses a loopback fake model and temporary
HOME/XDG locations. No account keys, real history, or paid models are used.
"""
import json,threading,sys,os,tempfile,subprocess,time,psutil,sqlite3
from pathlib import Path
from http.server import BaseHTTPRequestHandler,ThreadingHTTPServer
sys.path.insert(0,str(Path(__file__).resolve().parents[1]/'scripts'))
from job_control import run_process,cancellation,Cancelled
from opencode_support import configure,text_result
from providers import executable
CLI=executable('opencode')
if not CLI: raise SystemExit('Install OpenCode V2 to run these optional checks.')
seen=[]
class Handler(BaseHTTPRequestHandler):
 def log_message(self,*_):pass
 def do_POST(self):
  body=json.loads(self.rfile.read(int(self.headers.get('Content-Length',0))));seen.append(dict(body,_path=self.path))
  if MODE=='slow':time.sleep(20)
  msg={'id':'test','object':'chat.completion','created':int(time.time()),'model':'synthetic','choices':[{'index':0,'message':{'role':'assistant','content':'{"ok":true}'},'finish_reason':'stop'}],'usage':{'prompt_tokens':1,'completion_tokens':1,'total_tokens':2}}
  self.send_response(200)
  if body.get('stream'):
   self.send_header('Content-Type','text/event-stream');self.end_headers()
   chunk={'id':'test','object':'chat.completion.chunk','created':int(time.time()),'model':'synthetic','choices':[{'index':0,'delta':{'role':'assistant','content':'{"ok":true}'},'finish_reason':None}]}
   if MODE=='denied' and len(seen)==1:
    chunk['choices'][0]['delta']={'role':'assistant','tool_calls':[{'index':0,'id':'synthetic-denied-tool','type':'function','function':{'name':'shell','arguments':json.dumps({'command':'touch '+str(SENTINEL),'description':'Synthetic denied tool test'})}}]}
   self.wfile.write(('data: '+json.dumps(chunk)+'\n\ndata: '+json.dumps(dict(chunk,choices=[dict(index=0,delta={},finish_reason='tool_calls' if MODE=='denied' and len(seen)==1 else 'stop')]))+'\n\ndata: [DONE]\n\n').encode())
  else:self.send_header('Content-Type','application/json');self.end_headers();self.wfile.write(json.dumps(msg).encode())
MODE=sys.argv[1] if len(sys.argv)>1 else 'normal'
if MODE not in {'normal','slow','denied','inherited'}: raise SystemExit('Choose normal, slow, denied, or inherited.')
server=ThreadingHTTPServer(('127.0.0.1',0),Handler);threading.Thread(target=server.serve_forever,daemon=True).start()
with tempfile.TemporaryDirectory(prefix='skilldesk-opencode-local-') as raw:
 base=Path(raw);work=base/'work';work.mkdir();SENTINEL=work/'should-not-exist';env={k:v for k,v in os.environ.items() if not any(s in k.upper() for s in ('TOKEN','SECRET','API_KEY','AUTH'))}
 env.update(HOME=str(base),XDG_CONFIG_HOME=str(base/'config'),XDG_DATA_HOME=str(base/'data'),XDG_CACHE_HOME=str(base/'cache'),XDG_STATE_HOME=str(base/'state'))
 config=base/'config/opencode';config.mkdir(parents=True)
 (config/'AGENTS.md').write_text('SYNTHETIC_GLOBAL_RULE_MARKER. Never use real data.')
 (config/'opencode.json').write_text(json.dumps({'enabled_providers':['fixture'],'provider':{'fixture':{'npm':'@ai-sdk/openai-compatible','options':{'baseURL':f'http://127.0.0.1:{server.server_port}/v1'},'models':{'synthetic':{'name':'Synthetic','limit':{'context':32000,'output':4000}}}}}}))
 if MODE=='inherited':
  plugins=config/'plugins';plugins.mkdir()
  (plugins/'marker.ts').write_text("import {writeFileSync} from 'node:fs';writeFileSync("+json.dumps(str(base/'plugin-marker'))+",'loaded');export default {id:'skilldesk-synthetic-marker',setup(){}};")
  mcp=base/'mcp.py';mcp.write_text("import sys,json,pathlib\npathlib.Path("+repr(str(base/'mcp-marker'))+").write_text('started')\nfor line in sys.stdin:\n try:\n  m=json.loads(line)\n  if 'id' not in m: continue\n  result={'protocolVersion':m.get('params',{}).get('protocolVersion','2024-11-05'),'capabilities':{'tools':{}},'serverInfo':{'name':'fixture','version':'1'}} if m['method']=='initialize' else {'tools':[]}\n  print(json.dumps({'jsonrpc':'2.0','id':m['id'],'result':result}),flush=True)\n except Exception: pass\n")
  cfg=json.loads((config/'opencode.json').read_text());cfg['mcp']={'fixture':{'type':'local','command':[sys.executable,str(mcp)]}};(config/'opencode.json').write_text(json.dumps(cfg))
 configure(work,env)
 event=threading.Event();timer=None
 if MODE=='slow':timer=threading.Timer(2,event.set);timer.start()
 try:
  with cancellation(event):
   result=run_process([CLI,'run','--standalone','--format','json','--model','fixture/synthetic','--title','Skill-Desk synthetic fixture'],input='Return only {"ok":true}.',cwd=work,env=env,capture_output=True,text=True,timeout=25)
  assert MODE!='slow', 'The slow request should have been cancelled'
  assert result.returncode==0, result.stderr[:1000]
  assert json.loads(text_result(result.stdout))=={'ok':True}
  assert not SENTINEL.exists(), 'A denied tool executed'
  assert seen and not seen[0].get('tools'), 'Tools were advertised despite denial'
  assert 'SYNTHETIC_GLOBAL_RULE_MARKER' in json.dumps(seen), 'Update the recorded isolation finding'
  if MODE=='inherited': assert (base/'plugin-marker').exists() and (base/'mcp-marker').exists()
  print(json.dumps(dict(exit=result.returncode,stdout=result.stdout[:4000],stderr=result.stderr[:1500],requests=len(seen),sentinelCreated=SENTINEL.exists(),globalRuleIncluded='SYNTHETIC_GLOBAL_RULE_MARKER' in json.dumps(seen),tools=[t.get('function',{}).get('name') for t in (seen[0].get('tools',[]) if seen else [])],pluginLoaded=(base/'plugin-marker').exists(),mcpStarted=(base/'mcp-marker').exists())))
 except Cancelled as e:
  assert MODE=='slow' and seen
  print(json.dumps(dict(error=type(e).__name__,message=str(e),requests=len(seen),sentinelCreated=SENTINEL.exists(),globalRuleIncluded='SYNTHETIC_GLOBAL_RULE_MARKER' in json.dumps(seen),requestShape=[dict(path=b.get('_path'),keys=list(b),tools=[t.get('function',{}).get('name') for t in b.get('tools',[])]) for b in seen])))
 finally:
  if timer:timer.cancel()
  alive=[]
  for process in psutil.process_iter(['name']):
   try:
    if process.pid!=os.getpid() and process.environ().get('XDG_DATA_HOME')==str(base/'data'): alive.append(process.pid)
   except psutil.Error:pass
  print(json.dumps({'ownedProcessesRemaining':alive}))
  assert not alive, 'Owned CLI processes remain after completion'
  dbpath=base/'data/opencode/opencode.db'
  if dbpath.exists() and MODE=='normal':
   with sqlite3.connect(dbpath) as db: ids=[r[0] for r in db.execute('SELECT id FROM session_v2')]
   if ids:
    exported=subprocess.run([CLI,'session','export','--standalone',ids[0]],cwd=work,env=env,capture_output=True,text=True,timeout=15)
    deleted=subprocess.run([CLI,'session','delete','--standalone',ids[0]],cwd=work,env=env,capture_output=True,text=True,timeout=15)
    with sqlite3.connect(dbpath) as db: count=db.execute('SELECT count(*) FROM session_v2 WHERE id=?',(ids[0],)).fetchone()[0]
    assert exported.returncode==0 and exported.stdout.lstrip().startswith('{')
    assert deleted.returncode==0 and count==0
    print(json.dumps(dict(persistedSessions=len(ids),exportExit=exported.returncode,exportJSON=exported.stdout.lstrip().startswith('{'),deleteExit=deleted.returncode,remainingDeletedSession=count)))
server.shutdown()
