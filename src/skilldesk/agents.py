"""Supported local agents and their native skill destinations."""
import os
from pathlib import Path

LABELS = {'codex':'Codex', 'claude':'Claude Code', 'opencode':'OpenCode', 'cursor':'Cursor'}
PROJECT_FOLDERS = {'codex':'.agents', 'claude':'.claude', 'opencode':'.opencode', 'cursor':'.cursor'}
HISTORY_AGENTS = {'codex', 'claude'}


def personal_root(agent, home=None):
    home = home if home is not None else Path.home()
    if agent == 'codex': root = Path(os.environ.get('CODEX_HOME') or home/'.codex')
    elif agent == 'claude': root = Path(os.environ.get('CLAUDE_CONFIG_DIR') or home/'.claude')
    elif agent == 'opencode': root = Path(os.environ.get('XDG_CONFIG_HOME') or home/'.config')/'opencode'
    elif agent == 'cursor': root = home/'.cursor'
    else: raise ValueError('Choose a supported agent.')
    return (root.expanduser()/'skills').resolve()


def native_agent(root):
    root = Path(root).resolve()
    for agent, variable in [('codex','CODEX_HOME'),('claude','CLAUDE_CONFIG_DIR')]:
        if os.environ.get(variable) and root == (Path(os.environ[variable]).expanduser()/'skills').resolve(): return agent
    if root.parent.name == 'opencode': return 'opencode'
    if root.parent.name == '.codex': return 'codex'
    for agent, folder in PROJECT_FOLDERS.items():
        if root.parent.name == folder: return agent
    return 'codex'


def compatible_agents(root):
    agent = native_agent(root)
    # These agents document compatibility with the other skill directories.
    if agent == 'codex': return ['codex','cursor','opencode'] if Path(root).parent.name == '.agents' else ['codex','cursor']
    if agent == 'claude': return ['claude','cursor','opencode']
    return [agent]


def starter(agent, name, task):
    invocation = ('/' if agent in {'claude','cursor'} else '$') + name
    if agent == 'opencode': invocation = 'Use the '+name+' skill.'
    return invocation+' '+task.strip()
