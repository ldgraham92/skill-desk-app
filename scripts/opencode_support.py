"""Inspect the installed CLI without borrowing credentials or calling model APIs."""
import json
import re
import subprocess
import tempfile
from functools import lru_cache
from pathlib import Path
from job_control import run_process
from platform_support import command_prefix, subprocess_options


@lru_cache(maxsize=8)
def _capabilities(cli, modified):
    with tempfile.TemporaryDirectory(prefix='skilldesk-cli-check-') as work:
        result = run_process(command_prefix(cli)+['run','--help'], cwd=work,
                             capture_output=True, text=True, timeout=10, **subprocess_options())
    if result.returncode: raise ValueError('OpenCode command inspection failed. Check the CLI in Terminal.')
    return {'standalone': '--standalone' in result.stdout,
            'compatible': all(flag in result.stdout for flag in ('--format', '--model', '--title'))}


def capabilities(cli):
    return _capabilities(cli, Path(cli).stat().st_mtime_ns)


def configure(work, env):
    # The project file also applies to V2, which does not promise support for
    # every V1 environment override. This is authoring, not history isolation.
    config = {'permission': {'*': 'deny'}, 'share': 'disabled', 'snapshot': False}
    env['OPENCODE_CONFIG_CONTENT'] = json.dumps(config)
    folder = Path(work)/'.opencode'
    folder.mkdir(exist_ok=True)
    (folder/'opencode.json').write_text(json.dumps(config), encoding='utf-8')


def models(cli):
    caps = capabilities(cli)
    with tempfile.TemporaryDirectory(prefix='skilldesk-models-') as work:
        result = run_process(command_prefix(cli)+['models']+(['--standalone'] if caps['standalone'] else []),
                             cwd=work, capture_output=True, text=True, timeout=30, **subprocess_options())
    if result.returncode: raise ValueError('OpenCode could not list models. Check its model setup in Terminal and retry.')
    rows = []
    # CLI IDs are reliable. A name containing "free" is not pricing evidence.
    for line in result.stdout.splitlines():
        value=line.strip()
        if re.fullmatch(r'[A-Za-z0-9][A-Za-z0-9._-]*/[A-Za-z0-9._:/#-]+',value):
            rows.append(dict(id=value, free=None))
    rows=list({r['id']:r for r in rows}.values())[:3000]
    return dict(models=rows, message='' if rows else 'OpenCode returned no model IDs. Availability depends on its enabled providers and project configuration. Open /models inside OpenCode, then enter an available provider/model ID here.',
                pricing='The CLI does not provide verified pricing in this list. Check OpenCode before running a model.')


def text_result(stdout):
    """Accept text parts; reject errors even when a CLI exits successfully."""
    events=[json.loads(line) for line in stdout.splitlines() if line.strip()]
    for event in events:
        if not isinstance(event,dict): raise ValueError('Invalid OpenCode event.')
        if event.get('type')=='error':
            error=event.get('error',{})
            message=error.get('message','') if isinstance(error,dict) else str(error)
            # Imported lazily to avoid a provider import cycle.
            from providers import generation_error
            raise RuntimeError(generation_error('opencode',message))
    return ''.join(e.get('part',{}).get('text','') for e in events if e.get('type')=='text')
