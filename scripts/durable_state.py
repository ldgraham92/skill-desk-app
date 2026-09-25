"""Atomic local records with optimistic concurrency and preserved corrupt input."""
import hashlib
import json
import os
from pathlib import Path
import tempfile


def digest(path):
    try: return hashlib.sha256(Path(path).read_bytes()).hexdigest()
    except FileNotFoundError: return None


def atomic_bytes(path, value):
    path = Path(path)
    path.parent.mkdir(parents=True, exist_ok=True)
    fd, name = tempfile.mkstemp(prefix='.' + path.name + '-', dir=path.parent)
    try:
        with os.fdopen(fd, 'wb') as stream:
            stream.write(value)
            stream.flush()
            os.fsync(stream.fileno())
        os.replace(name, path)
        if os.name != 'nt':
            directory = os.open(path.parent, os.O_RDONLY)
            try: os.fsync(directory)
            finally: os.close(directory)
    finally:
        if os.path.exists(name): os.unlink(name)


def atomic_json(path,value):
    atomic_bytes(path,json.dumps(value,ensure_ascii=False,indent=2).encode('utf-8'))


class StateFile:
    def __init__(self, path, default):
        self.path = Path(path)
        self.revision = digest(self.path)
        self.error = ''
        try:
            self.value = json.loads(self.path.read_text(encoding='utf-8'))
            if not isinstance(self.value, type(default)): raise ValueError('Unexpected record type')
        except FileNotFoundError: self.value = default
        except (ValueError, UnicodeError, OSError) as error:
            self.value = default
            self.error = 'Saved state cannot be read: ' + self.path.name + '. The original file is preserved. ' + str(error)

    def save(self, value):
        if self.error: raise ValueError(self.error)
        if digest(self.path) != self.revision:
            raise ValueError('Saved state changed in another process. Restart Skill-Desk before changing ' + self.path.name + '.')
        atomic_json(self.path, value)
        self.revision = digest(self.path)
        self.value = value
