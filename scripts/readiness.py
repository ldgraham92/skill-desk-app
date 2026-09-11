"""Check CLI execution and saved authentication without making inference requests."""
from concurrent.futures import ThreadPoolExecutor
import json
import os
import re
import subprocess
import tempfile
from providers import executable,LABELS
from platform_support import command_prefix,subprocess_options

def check_agent(name):
    result=dict(id=name,label=LABELS[name],installed=False,signedIn=None,compatible=None,status='missing',version='',message='Install this CLI, sign in, and check again.',command='codex login' if name=='codex' else 'claude auth login')
    cli=executable(name)
    if not cli:return result
    result['installed']=True
    try:
        with tempfile.TemporaryDirectory(prefix='skilldesk-readiness-') as work:
            env=dict(os.environ)
            if name=='claude':
                for key in ['ANTHROPIC_API_KEY','ANTHROPIC_AUTH_TOKEN','CLAUDE_CODE_OAUTH_TOKEN','ANTHROPIC_BASE_URL','CLAUDE_CODE_USE_BEDROCK','CLAUDE_CODE_USE_VERTEX','CLAUDE_CODE_USE_FOUNDRY']:env.pop(key,None)
            def run(args):return subprocess.run(command_prefix(cli)+args,cwd=work,env=env,text=True,encoding='utf-8',stdout=subprocess.PIPE,stderr=subprocess.PIPE,timeout=8,**subprocess_options())
            version=run(['--version']);match=re.search(r'\b\d+\.\d+\.\d+(?:[-.][\w.]+)?',version.stdout)
            if version.returncode:raise ValueError('CLI did not start')
            result['version']=match.group(0) if match else 'Unknown version'
            help_result=run(['exec','--help'] if name=='codex' else ['--help'])
            needed=['--ignore-user-config','--ephemeral','--output-schema'] if name=='codex' else ['--setting-sources','--strict-mcp-config','--disable-slash-commands','--json-schema']
            result['compatible']=True if help_result.returncode==0 and all(flag in help_result.stdout for flag in needed) else None
            if name=='claude' and match and int(match.group(0).split('.')[0])<2:
                result.update(status='update',message='Update Claude Code before checking saved authentication.',command='claude update');return result
            auth=run(['login','status'] if name=='codex' else ['auth','status'])
            if name=='claude':
                data=json.loads(auth.stdout);result['signedIn']=data.get('loggedIn') if type(data.get('loggedIn')) is bool else None
            else:
                text=(auth.stdout+auth.stderr).lower()
                result['signedIn']=True if auth.returncode==0 and 'logged in' in text else False if 'not logged in' in text else None
        if result['compatible'] is False:result.update(status='update',message='Update this CLI to use Skill-Desk’s isolated recommendation review.',command='codex --help' if name=='codex' else 'claude update')
        elif result['signedIn'] is True:result.update(status='ready',message='CLI starts and reports a saved sign-in. Service access, configuration support, and usage limits are checked when you run a task.',command='')
        elif result['signedIn'] is False:result.update(status='sign-in',message='The CLI is installed but reports no saved sign-in. Run the command below in Terminal.')
        else:result.update(status='unknown',message='Could not confirm sign-in. Check the CLI in Terminal, then retry.')
    except (OSError,ValueError,subprocess.TimeoutExpired,RuntimeError):result.update(status='unknown',message='The CLI check did not complete. Open it in Terminal, confirm it starts, and retry.')
    return result

def check_all():
    with ThreadPoolExecutor(max_workers=2) as pool:return list(pool.map(check_agent,['codex','claude']))
