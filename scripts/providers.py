"""Structured authoring through installed, authenticated command-line clients."""
import json
import os
from pathlib import Path
import shutil
import subprocess
import tempfile
import threading
import re
import time
import opencode_support
from job_control import run_process
from agents import LABELS, HISTORY_AGENTS, personal_root, PROJECT_FOLDERS, compatible_agents

from platform_support import data_dir, command_prefix, subprocess_options
SETTINGS = data_dir()/'provider.json'


def executable(name):
    if name == 'cursor':
        return executable('cursor-agent') or executable('agent')
    found = shutil.which(name)
    if found: return found
    directories=[Path.home()/p for p in ('.local/bin','.cargo/bin','.opencode/bin','.bun/bin','.npm-global/bin')]
    directories += [Path('/opt/homebrew/bin'),Path('/usr/local/bin')]
    if os.name=='nt':
        directories += [Path(os.environ.get('APPDATA') or Path.home()/'AppData/Roaming')/'npm',Path(os.environ.get('LOCALAPPDATA') or Path.home()/'AppData/Local')/'Programs/Claude']
    for directory in directories:
        for suffix in (('.exe','.cmd','') if os.name=='nt' else ('',)):
            candidate=directory/(name+suffix)
            if candidate.is_file() and os.access(candidate,os.X_OK): return str(candidate)
    return None


def valid_model(name,model):
    return isinstance(model,str) and len(model)<=160 and (not model or bool(re.fullmatch(r'[A-Za-z0-9][A-Za-z0-9._:/#-]*',model))) and (name!='opencode' or not model or ('/' in model and not model.endswith('/')))


def generation_error(name,output,analysis=False):
    text=output.lower()
    if 'free tier can only be used' in text:
        reason='OpenCode rejected free-tier access for this CLI request. Try the same model in OpenCode and check its setup. No paid model was substituted.'
    elif any(s in text for s in ('unauthorized','not logged in','authentication','401','sign in','login required')):
        reason='Your saved sign-in was rejected. Sign in again in Terminal and retry.'
    elif any(s in text for s in ('rate limit','usage limit','free usage','quota','429')):
        reason='The account has reached a usage limit. Check the installed tool and retry after its limit resets.'
    elif any(s in text for s in ('model not found','unknown model','invalid model','model is not available','modelnotfound','not supported')):
        reason='The selected model is unavailable. Choose a model supported by your signed-in tool, or clear the model setting.'
    elif any(s in text for s in ('unknown option','unexpected argument','unrecognized argument')):
        reason='The installed CLI does not support a required option. Update it, check readiness, and retry.'
    elif any(s in text for s in ('connection refused','network','fetch failed','timed out','dns')):
        reason='The model service could not be reached. Check your connection and retry the preserved draft.'
    else: reason='Check the CLI sign-in, connection, model, and usage limits in Terminal, then retry.'
    if analysis: reason+=' History review requires isolated configuration support.'
    return LABELS[name]+' could not finish. '+reason


class AuthorProvider:
    def __init__(self, settings=SETTINGS):
        self.settings, self.lock = settings, threading.Lock()
        self.connection_tests = {}
        try:
            saved=json.loads(settings.read_text(encoding='utf-8'))
            if not isinstance(saved,dict): saved={}
        except (OSError,ValueError): saved={}
        self.name=saved.get('provider')
        if not isinstance(self.name,str) or self.name not in LABELS:
            self.name=next((name for name in LABELS if executable(name)), 'codex')
        models=saved.get('models',{})
        self.models={name:model for name,model in models.items() if name in LABELS and valid_model(name,model)} if isinstance(models,dict) else {}

    @property
    def label(self): return LABELS[self.name]

    def snapshot(self):
        return {'selected': self.name, 'models':self.models, 'connectionTests':self.connection_tests, 'providers': [{'id': n, 'label': label, 'installed': bool(executable(n)), 'historyAnalysis':n in HISTORY_AGENTS,'authoring':True,'company':{'codex':'OpenAI','claude':'Anthropic','opencode':'Configured providers, including DeepSeek','cursor':'Cursor'}[n],'personalRoot':str(personal_root(n)),'projectFolder':PROJECT_FOLDERS[n]+'/skills','discoverableBy':compatible_agents(personal_root(n))} for n,label in LABELS.items()]}

    def select(self, name, model=None):
        if not isinstance(name,str) or name not in LABELS: raise ValueError('Choose a supported authoring agent.')
        if model is not None and not valid_model(name,model):
            raise ValueError('Enter a provider/model ID for OpenCode or a model ID for the selected CLI. Leave it empty to use the CLI default.')
        if not executable(name): raise ValueError(f'{LABELS[name]} CLI is not installed. Install it and sign in in Terminal first.')
        with self.lock:
            if model is not None: self.models[name]=model
            self.settings.parent.mkdir(parents=True, exist_ok=True)
            tmp = self.settings.with_suffix('.tmp');tmp.write_text(json.dumps({'provider':name,'models':self.models}), encoding='utf-8');tmp.replace(self.settings)
            self.name = name
        return self.snapshot()

    def __call__(self, prompt, schema_data):
        return self.generate(prompt, schema_data)

    def generate(self, prompt, schema_data, provider=None, analysis=False, model_override=None):
        name = provider or self.name
        if not isinstance(name,str) or name not in LABELS: raise ValueError('Choose a supported authoring agent.')
        if analysis and name not in HISTORY_AGENTS:
            raise ValueError('Isolated history analysis is not yet supported for '+LABELS[name]+'. Skill authoring and installation are available.')
        cli = executable(name)
        if not cli: raise RuntimeError(f'{LABELS[name]} CLI was not found. Install it, sign in, then retry.')
        with tempfile.TemporaryDirectory(prefix='skill-desk-author-') as tmp:
            tmp = Path(tmp); output = tmp/'result.json'
            env = dict(os.environ)
            for key in ('OPENAI_API_KEY','OPENAI_BASE_URL','ANTHROPIC_API_KEY','ANTHROPIC_AUTH_TOKEN','CLAUDE_CODE_OAUTH_TOKEN','ANTHROPIC_BASE_URL','DEEPSEEK_API_KEY','CURSOR_API_KEY'):
                env.pop(key,None)
            if name == 'codex':
                schema = tmp/'schema.json';schema.write_text(json.dumps(schema_data), encoding='utf-8')
                cmd = command_prefix(cli) + ['exec','--ephemeral','--skip-git-repo-check','--sandbox','read-only','-C',str(tmp),'--output-schema',str(schema),'-o',str(output),'-']
            elif name == 'claude':
                # Use the saved CLI login rather than an inherited API-billing override.
                for key in ['ANTHROPIC_API_KEY','ANTHROPIC_AUTH_TOKEN','CLAUDE_CODE_OAUTH_TOKEN','ANTHROPIC_BASE_URL','CLAUDE_CODE_USE_BEDROCK','CLAUDE_CODE_USE_VERTEX','CLAUDE_CODE_USE_FOUNDRY']:
                    env.pop(key,None)
                cmd = command_prefix(cli) + ['--print','--output-format','json','--json-schema',json.dumps(schema_data),'--no-session-persistence','--tools','','--disallowedTools','mcp__*']
            elif name == 'opencode':
                # Keep the CLI's authentication and model configuration. Deny tools
                # for this authoring run; no user history is supplied to this path.
                caps=opencode_support.capabilities(cli)
                if not caps['compatible']: raise ValueError('Update OpenCode: required run options are unavailable.')
                opencode_support.configure(tmp,env)
                cmd=command_prefix(cli)+['run']+(['--standalone'] if caps['standalone'] else [])+['--format','json','--title','Skill-Desk skill authoring']
            else:
                config=tmp/'.cursor';config.mkdir()
                (config/'cli.json').write_text(json.dumps({'permissions':{'allow':[],'deny':['Shell(*)','Read(**)','Write(**)','WebFetch(*)','Mcp(*:*)']}}),encoding='utf-8')
                cmd=command_prefix(cli)+['--print','--mode','ask','--output-format','json','--workspace',str(tmp)]
            model=self.models.get(name) if model_override is None else model_override
            if not valid_model(name,model or ''): raise ValueError('Invalid model ID.')
            if isinstance(model,str) and model: cmd+=['--model',model]
            if name in {'opencode','cursor'}:
                prompt+='\nReturn only a JSON object, without Markdown fences, matching this JSON schema:\n'+json.dumps(schema_data)
            if analysis:
                if name == 'codex':
                    cmd += ['--ignore-user-config', '--disable', 'shell_tool', '--disable', 'apps', '--disable', 'plugins', '--disable', 'hooks', '--disable', 'multi_agent', '-c', 'web_search="disabled"', '-c', 'features.skip_host_skill_discovery=true']
                else:
                    cmd += ['--setting-sources', '', '--strict-mcp-config', '--mcp-config', '{"mcpServers":{}}', '--disable-slash-commands']
            try:
                run = run_process(cmd,input=prompt,text=True,stdout=subprocess.PIPE,stderr=subprocess.PIPE,cwd=tmp,env=env,timeout=300,encoding="utf-8",**subprocess_options())
            except subprocess.TimeoutExpired:
                raise RuntimeError(LABELS[name]+' did not finish within five minutes. The process was stopped. Your draft is preserved for retry.') from None
            if name=='opencode':
                try: opencode_support.text_result(run.stdout)
                except RuntimeError: raise
                except (ValueError,TypeError,AttributeError): pass
            if run.returncode: raise RuntimeError(generation_error(name,run.stderr or '',analysis))
            if name == 'codex':
                if not output.exists(): raise ValueError('Codex did not return a structured result.')
                try: result = json.loads(output.read_text(encoding='utf-8'))
                except (ValueError,UnicodeError): raise ValueError('Codex returned incomplete JSON. Retry the preserved draft.') from None
            elif name == 'claude':
                try:
                    envelope = json.loads(run.stdout)
                    if not isinstance(envelope,dict): raise ValueError()
                except (ValueError,TypeError): raise ValueError('Claude Code returned incomplete JSON. Retry the preserved draft.') from None
                if envelope.get('is_error'): raise RuntimeError(generation_error(name,str(envelope.get('result','')),analysis))
                result = envelope.get('structured_output')
                if not isinstance(result,dict): raise ValueError('Claude Code did not return structured_output. Update Claude Code and retry.')
            else:
                try:
                    if name=='cursor':
                        envelope=json.loads(run.stdout)
                        if envelope.get('is_error') or envelope.get('subtype')!='success': raise ValueError()
                        content=envelope['result']
                    else:
                        content=opencode_support.text_result(run.stdout)
                    result=json.loads(content)
                except (ValueError,KeyError,TypeError,AttributeError):
                    raise ValueError(LABELS[name]+' did not return a complete JSON result. Retry with a model that supports structured output.') from None
            if not isinstance(result,dict): raise ValueError('Authoring returned an invalid JSON object.')
            return result

    def test_connection(self,data,progress):
        name=data.get('provider',self.name)
        if name not in LABELS: raise ValueError('Choose a supported agent.')
        model=data.get('model',self.models.get(name,''))
        if not valid_model(name,model): raise ValueError('Invalid model ID.')
        progress('testing','Sending a synthetic connection test to '+LABELS[name])
        try:
            output=self.generate('Connection test. Do not use tools. Return only {"ok":true}.',
                {'type':'object','properties':{'ok':{'type':'boolean'}},'required':['ok'],'additionalProperties':False},provider=name,model_override=model)
            if output!={'ok':True}: raise ValueError('The model responded but did not pass the structured response check.')
        except Exception:
            self.connection_tests[name]=dict(provider=name,model=model,checkedAt=time.time(),status='failed')
            raise
        result=dict(provider=name,model=model,checkedAt=time.time(),status='tested')
        self.connection_tests[name]=result
        return dict(connectionTest=result)
