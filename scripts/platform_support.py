"""Platform paths, locking and subprocess behavior for packaged desktop launches."""
import os
from pathlib import Path
import sys
import shutil

def data_dir():
    if os.environ.get('SKILL_DESK_HOME'): return Path(os.environ['SKILL_DESK_HOME'])
    if sys.platform == 'win32': return Path(os.environ.get('LOCALAPPDATA', Path.home()/'AppData/Local'))/'Skill-Desk'
    if sys.platform == 'darwin': return Path.home()/'Library/Application Support/Skill-Desk'
    return Path(os.environ.get('XDG_DATA_HOME', Path.home()/'.local/share'))/'Skill-Desk'

def cache_dir():
    if os.environ.get('SKILL_DESK_HOME'): return data_dir()/'Cache'
    if sys.platform == 'darwin': return Path.home()/'Library/Caches/Skill-Desk'
    if sys.platform == 'win32': return data_dir()/'Cache'
    return Path(os.environ.get('XDG_CACHE_HOME', Path.home()/'.cache'))/'Skill-Desk'

def lock_file(path):
    handle = open(path, 'a+b')
    try:
        if sys.platform == 'win32':
            import msvcrt
            handle.seek(0); handle.write(b'0'); handle.flush(); handle.seek(0)
            msvcrt.locking(handle.fileno(), msvcrt.LK_NBLCK, 1)
        else:
            import fcntl
            fcntl.flock(handle, fcntl.LOCK_EX | fcntl.LOCK_NB)
    except OSError:
        handle.close()
        raise RuntimeError('Skill-Desk is already running. Quit the other instance first.')
    return handle

def prepare_path():
    extra = [Path.home()/'.local/bin', Path.home()/'.cargo/bin', Path('/opt/homebrew/bin'), Path('/usr/local/bin')]
    if sys.platform == 'win32':
        extra += [Path(os.environ.get('APPDATA', Path.home()/'AppData/Roaming'))/'npm', Path(os.environ.get('LOCALAPPDATA', Path.home()/'AppData/Local'))/'Programs/Claude', Path(os.environ.get('ProgramFiles', 'C:/Program Files'))/'Git/cmd']
    os.environ['PATH'] = os.pathsep.join([os.environ.get('PATH','')] + [str(p) for p in extra if p.is_dir()])

def command_prefix(cli):
    # npm installs command shims on Windows. Invoke their JS entrypoint without
    # cmd.exe so prompts and schema arguments never undergo shell expansion.
    path = Path(cli)
    if sys.platform == 'win32' and path.suffix.lower() in {'.cmd', '.bat'}:
        node = shutil.which('node')
        package = {'codex': '@openai/codex/bin/codex.js', 'claude': '@anthropic-ai/claude-code/cli.js'}.get(path.stem)
        entry = path.parent/'node_modules'/package if package else None
        if node and entry and entry.is_file(): return [node, str(entry)]
        raise RuntimeError('CLI shim could not be resolved. Install the native CLI or a standard npm installation.')
    return [cli]

def subprocess_options():
    return {'creationflags': 0x08000000} if sys.platform == 'win32' else {}

prepare_path()
