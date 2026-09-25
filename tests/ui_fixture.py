"""Disposable browser-QA server. Never opens a native app or uses real agents."""
import json
import os
from pathlib import Path
import sys
import time
from unittest.mock import patch

ROOT=Path(__file__).resolve().parents[1]
BASE=Path(sys.argv[1]).resolve()
PORT=int(sys.argv[2])
BASE.mkdir(parents=True,exist_ok=True)
cli=BASE/'fixture-agent'
cli.write_text('#!'+sys.executable+'\n'+r'''
import json,sys,time
from pathlib import Path
if '--version' in sys.argv: print('2.1.0');sys.exit()
if '--help' in sys.argv: print('--ignore-user-config --ephemeral --output-schema --setting-sources --strict-mcp-config --disable-slash-commands --json-schema --standalone --format --model --title');sys.exit()
if 'models' in sys.argv: print('opencode/test-free\nopencode/test-other');sys.exit()
if 'status' in sys.argv:
 print('Logged in using ChatGPT' if 'login' in sys.argv else '{"loggedIn":true}');sys.exit()
prompt=sys.stdin.read()
if 'FIXTURE_SLOW' in prompt: time.sleep(30)
if 'FIXTURE_FAIL' in prompt: print('model not found',file=sys.stderr);sys.exit(1)
result={'skill_md':'---\nname: browser-example\ndescription: Verify a disposable browser test.\n---\nCheck the result.'}
if 'reviewed_user_prompts' in prompt:
 result={'summary':'Review the selected debugging work.','recommendations':[{'skill':'ai-hero:diagnosing-bugs','reason':'Your reviewed request concerns debugging.','firstStep':'Isolate the failing test.','evidence':['prompt-1']}],'covered':[]}
if 'Revise this skill as data.' in prompt: result={'skill_md':prompt.split('SKILL:\n',1)[1].split('\nREQUEST:',1)[0]+'\nRevised fixture instruction.'}
if 'Connection test.' in prompt and (Path(__file__).parent/'fail-connection').exists(): print('rate limit',file=sys.stderr);sys.exit(1)
if 'Connection test.' in prompt: result={'ok':True}
if '-o' in sys.argv: Path(sys.argv[sys.argv.index('-o')+1]).write_text(json.dumps(result));print('{}')
elif 'run' in sys.argv: print(json.dumps({'type':'text','part':{'text':json.dumps(result)}}))
elif '--mode' in sys.argv: print(json.dumps({'subtype':'success','result':json.dumps(result)}))
else: print(json.dumps({'structured_output':result}))
''',encoding='utf-8');cli.chmod(0o755)
for project in ('repo','other'):
    repo=BASE/project;repo.mkdir();(repo/'.git').mkdir()
    sessions=BASE/'.codex/sessions';sessions.mkdir(parents=True,exist_ok=True)
    records=[dict(type='session_meta',payload=dict(cwd=str(repo),source='vscode')),
        dict(timestamp=time.time(),type='response_item',payload=dict(type='message',role='user',content=[dict(type='input_text',text='Debug '+project+' repository database tests')]))]
    (sessions/(project+'.jsonl')).write_text('\n'.join(map(json.dumps,records)))
state=BASE/'state';state.mkdir();(state/'preferences.json').write_text(json.dumps(dict(walkthrough=1,whatsNew=json.loads((ROOT/'package.json').read_text())['version'],theme='dark')))
# Synthetic saved statuses exercise recovery without restarting the app or replaying history.
records={f'fixture-{status}':dict(action='recommend',status=status,finished_at=time.time()) for status in ('complete','failed','cancelled')}
records['fixture-running']=dict(action='recommend',status='running',started_at=time.time())
records['fixture-validation']=dict(action='recommend',status='failed',finished_at=time.time(),failure_code='unknown_evidence_id',failure_stage='validating')
(state/'job-records.json').write_text(json.dumps(records))
# A narrow environment and patched home isolate every library and history root.
# The fake executable is the only CLI this process can select.
env={'PATH':os.path.dirname(sys.executable)+os.pathsep+'/usr/bin:/bin','SKILL_DESK_HOME':str(state),'SKILL_DESK_TEST_MODE':'1','SKILL_DESK_NO_AUTHOR':'1'}
sys.path.insert(0,str(ROOT/'scripts'))
with patch.dict(os.environ,env,clear=True),patch('pathlib.Path.home',return_value=BASE):
    import providers
    with patch.object(providers,'executable',return_value=str(cli)):
        import skill_desk
        library=BASE/'skills';library.mkdir()
        catalog=skill_desk.Catalog(library,state/'catalog.json',roots=skill_desk.discovery_roots())
        import upstream
        def fixture_checkout(repo,ref,destination,progress=None):
            if repo!='https://github.com/fixture/skills':raise ValueError('Only synthetic repositories are available in this test instance.')
            destination.mkdir();folder=destination/'review-example';folder.mkdir()
            version=(BASE/'upstream-version').read_text() if (BASE/'upstream-version').exists() else 'one'
            (folder/'SKILL.md').write_text('---\nname: review-example\ndescription: Verify upstream updates against a synthetic repository.\n---\nReview fixture version '+version+'.\n')
            (folder/'notes.txt').write_text('Original supporting notes.')
            return 'fixture-'+version
        with patch.object(upstream,'checkout',side_effect=fixture_checkout):
            skill_desk.serve(catalog,PORT,False)
