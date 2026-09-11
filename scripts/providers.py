"""Structured authoring through installed, authenticated command-line clients."""
import json
import os
from pathlib import Path
import shutil
import subprocess
import tempfile
import threading

LABELS = {'codex': 'Codex', 'claude': 'Claude Code'}
from platform_support import data_dir, command_prefix, subprocess_options
SETTINGS = data_dir()/'provider.json'


def executable(name):
    found = shutil.which(name)
    if found: return found
    candidate = Path.home()/'.local/bin'/name
    return str(candidate) if candidate.is_file() and os.access(candidate, os.X_OK) else None


class AuthorProvider:
    def __init__(self, settings=SETTINGS):
        self.settings, self.lock = settings, threading.Lock()
        try: self.name = json.loads(settings.read_text(encoding='utf-8'))['provider']
        except (OSError, ValueError, KeyError): self.name = 'codex' if executable('codex') else 'claude'
        if self.name not in LABELS: self.name = 'codex'

    @property
    def label(self): return LABELS[self.name]

    def snapshot(self):
        return {'selected': self.name, 'providers': [{'id': n, 'label': label, 'installed': bool(executable(n))} for n,label in LABELS.items()]}

    def select(self, name):
        if name not in LABELS: raise ValueError('Choose Codex or Claude Code.')
        if not executable(name): raise ValueError(f'{LABELS[name]} CLI is not installed. Install it and sign in in Terminal first.')
        with self.lock:
            self.settings.parent.mkdir(parents=True, exist_ok=True)
            tmp = self.settings.with_suffix('.tmp');tmp.write_text(json.dumps({'provider':name}), encoding='utf-8');tmp.replace(self.settings)
            self.name = name
        return self.snapshot()

    def __call__(self, prompt, schema_data):
        return self.generate(prompt, schema_data)

    def generate(self, prompt, schema_data, provider=None, analysis=False):
        name = provider or self.name
        if name not in LABELS: raise ValueError('Choose Codex or Claude Code.')
        cli = executable(name)
        if not cli: raise RuntimeError(f'{LABELS[name]} CLI was not found. Install it, sign in, then retry.')
        with tempfile.TemporaryDirectory(prefix='skill-desk-author-') as tmp:
            tmp = Path(tmp); output = tmp/'result.json'
            env = dict(os.environ)
            if name == 'codex':
                schema = tmp/'schema.json';schema.write_text(json.dumps(schema_data), encoding='utf-8')
                cmd = command_prefix(cli) + ['exec','--ephemeral','--skip-git-repo-check','--sandbox','read-only','-C',str(tmp),'--output-schema',str(schema),'-o',str(output),'-']
            else:
                # Use the saved CLI login rather than an inherited API-billing override.
                for key in ['ANTHROPIC_API_KEY','ANTHROPIC_AUTH_TOKEN','CLAUDE_CODE_OAUTH_TOKEN','ANTHROPIC_BASE_URL','CLAUDE_CODE_USE_BEDROCK','CLAUDE_CODE_USE_VERTEX','CLAUDE_CODE_USE_FOUNDRY']:
                    env.pop(key,None)
                cmd = command_prefix(cli) + ['--print','--output-format','json','--json-schema',json.dumps(schema_data),'--no-session-persistence','--tools','','--disallowedTools','mcp__*']
            if analysis:
                if name == 'codex':
                    cmd += ['--ignore-user-config', '--disable', 'shell_tool', '--disable', 'apps', '--disable', 'plugins', '--disable', 'hooks', '--disable', 'multi_agent', '-c', 'web_search="disabled"', '-c', 'features.skip_host_skill_discovery=true']
                else:
                    cmd += ['--setting-sources', '', '--strict-mcp-config', '--mcp-config', '{"mcpServers":{}}', '--disable-slash-commands']
            run = subprocess.run(cmd,input=prompt,text=True,stdout=subprocess.PIPE,stderr=subprocess.PIPE,cwd=tmp,env=env,timeout=300,encoding="utf-8",**subprocess_options())
            if run.returncode: raise RuntimeError(f'{LABELS[name]} generation failed. Check CLI sign-in and usage limits. '+('This analysis requires a current CLI with isolated configuration support.' if analysis else run.stderr[-1000:]))
            if name == 'codex':
                if not output.exists(): raise ValueError('Codex did not return a structured result.')
                result = json.loads(output.read_text(encoding='utf-8'))
            else:
                envelope = json.loads(run.stdout)
                if envelope.get('is_error'): raise RuntimeError('Claude Code could not complete generation. '+('Check CLI sign-in and usage limits, then retry.' if analysis else str(envelope.get('result','Unknown error'))[:1000]))
                result = envelope.get('structured_output')
                if not isinstance(result,dict): raise ValueError('Claude Code did not return structured_output. Update Claude Code and retry.')
            if not isinstance(result,dict): raise ValueError('Authoring returned an invalid JSON object.')
            return result
