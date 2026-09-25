"""Durable filesystem operation records. Recovery always requires a reviewed choice."""
import json
from pathlib import Path
import shutil
import time
import uuid
from durable_state import atomic_json,digest
from experience import tree_digest


class Transactions:
    def __init__(self, state):
        self.root = Path(state) / 'transactions'
        self.root.mkdir(exist_ok=True)

    def begin_file(self,action,destination,source):
        destination,source=Path(destination),Path(source)
        if destination.is_symlink() or source.is_symlink():raise ValueError('Settings recovery does not follow symbolic links.')
        token=uuid.uuid4().hex;base=self.root/token;base.mkdir()
        row=dict(id=token,action=action,destination=str(destination),resolvedParent=str(destination.parent.resolve()),started=time.time(),phase='prepared',fileMode=True,before=digest(destination),after=digest(source),origin={})
        try:
            if destination.exists():shutil.copy2(destination,base/'before')
            shutil.copy2(source,base/'after')
            if digest(base/'before')!=row['before'] or digest(base/'after')!=row['after'] or digest(destination)!=row['before']:raise ValueError('Settings changed while preparing recovery.')
            atomic_json(base/'record.json',row)
        except BaseException:
            if not (base/'record.json').exists():shutil.rmtree(base,ignore_errors=True)
            raise
        return row

    def begin(self, action, destination, source=None, origin=None):
        token = uuid.uuid4().hex
        base = self.root / token
        base.mkdir()
        destination = Path(destination)
        row = dict(id=token, action=action, destination=str(destination), resolvedParent=str(destination.parent.resolve()),
                   started=time.time(), phase='preparing', before=None, after=None, origin=origin or {})
        try:
            if destination.is_symlink():
                import os
                row['beforeLink']=os.readlink(destination)
            elif destination.exists():
                row['before'] = tree_digest(destination)
                shutil.copytree(destination, base / 'before')
                if tree_digest(base / 'before') != row['before'] or tree_digest(destination) != row['before']:
                    raise ValueError('Destination changed while preparing its recovery copy.')
            if source and Path(source).is_symlink():
                import os
                row['afterLink']=os.readlink(source)
            elif source:
                source = Path(source)
                row['after'] = tree_digest(source)
                shutil.copytree(source, base / 'after')
                if tree_digest(base / 'after') != row['after'] or tree_digest(source) != row['after']:
                    raise ValueError('Source changed during copy. Review it again.')
            row['phase'] = 'prepared'
            atomic_json(base / 'record.json', row)
            return row
        except BaseException:
            if not (base/'record.json').exists():shutil.rmtree(base,ignore_errors=True)
            raise

    def phase(self, row, phase):
        row = dict(row, phase=phase, updated=time.time())
        atomic_json(self.root / row['id'] / 'record.json', row)
        return row

    def records(self):
        result = []
        for file in self.root.glob('*/record.json'):
            try: result.append(json.loads(file.read_text(encoding='utf-8')))
            except (ValueError, OSError): result.append(dict(id=file.parent.name, phase='corrupt', message='Unreadable operation record; files preserved.'))
        return sorted(result, key=lambda r:r.get('started',0), reverse=True)

    def preview(self, token):
        if not isinstance(token,str) or len(token)!=32 or any(c not in '0123456789abcdef' for c in token): raise ValueError('Invalid operation record.')
        row = json.loads((self.root / token / 'record.json').read_text(encoding='utf-8'))
        if row['phase'] in {'complete','recovered'}: raise ValueError('This operation is already finished.')
        dest = Path(row['destination'])
        if dest.is_symlink() or str(dest.parent.resolve()) != row['resolvedParent']: raise ValueError('Recovery destination changed. Files are preserved.')
        current = (digest(dest) if row.get('fileMode') else tree_digest(dest)) if dest.exists() else None
        if row.get('beforeLink') or row.get('afterLink'):raise ValueError('This operation involved a directory link. Use its preserved archive and reconnect the link manually.')
        return dict(row,current=current,diverged=current not in {row['before'],row['after'],None},canRestore=row['before'] is not None,canFinish=row['after'] is not None)

    def recover(self, token, expected, mode):
        row = self.preview(token)
        if row['current'] != expected: raise ValueError('Destination changed after recovery review.')
        if mode not in {'before','after'} or row[mode] is None: raise ValueError('Choose an available recovery copy.')
        source = self.root / token / mode
        measure=digest if row.get('fileMode') else tree_digest
        if measure(source) != row[mode]: raise ValueError('Recovery copy failed verification. Files are preserved.')
        dest = Path(row['destination'])
        scratch = dest.parent / ('.skilldesk-recovery-' + uuid.uuid4().hex)
        displaced = self.root / token / ('displaced-' + uuid.uuid4().hex)
        dest.parent.mkdir(parents=True,exist_ok=True)
        if row.get('fileMode'):shutil.copy2(source,scratch)
        else:shutil.copytree(source, scratch)
        try:
            if measure(scratch)!=row[mode]: raise ValueError('Recovery copy changed during copying.')
            if (measure(dest) if dest.exists() else None)!=expected: raise ValueError('Destination changed during recovery.')
            if dest.exists(): shutil.move(str(dest),str(displaced))
            scratch.rename(dest)
        except BaseException:
            if displaced.exists() and not dest.exists(): shutil.move(str(displaced),str(dest))
            raise
        finally:
            if scratch.is_file():scratch.unlink()
            elif scratch.exists(): shutil.rmtree(scratch)
        return self.phase(row,'recovered')
