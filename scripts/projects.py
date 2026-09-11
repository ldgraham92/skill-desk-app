"""Persist explicitly onboarded repositories without modifying their contents."""
import json
from pathlib import Path
import secrets
import threading


def project_destination(path, agent):
    root=Path(path)
    if agent not in ('codex','claude'): raise ValueError('Choose Codex or Claude Code for this project.')
    if not root.is_dir() or root.is_symlink() or not (root/'.git').exists(): raise ValueError('Project is unavailable. Reconnect its repository before installing.')
    destination=root/('.agents' if agent=='codex' else '.claude')/'skills'
    for part in (destination.parent,destination):
        if part.is_symlink() or (part.exists() and not part.is_dir()): raise ValueError('Project skill directories must be ordinary folders inside the repository.')
    if not destination.resolve().is_relative_to(root.resolve()): raise ValueError('Project skill directory is outside the repository.')
    return destination


class Projects:
    def __init__(self,state):
        self.file=Path(state)/'projects.json';self.lock=threading.RLock()
        try:
            value=json.loads(self.file.read_text(encoding='utf-8'))
            self.items=[p for p in value if isinstance(p,dict) and all(isinstance(p.get(k),str) for k in ('id','name','path'))] if isinstance(value,list) else []
        except (OSError,ValueError): self.items=[]

    def save(self):
        self.file.parent.mkdir(parents=True,exist_ok=True)
        tmp=self.file.with_suffix('.tmp');tmp.write_text(json.dumps(self.items,indent=2),encoding='utf-8');tmp.replace(self.file)

    def listing(self):
        with self.lock:
            return [dict(p,available=Path(p['path']).is_dir() and (Path(p['path'])/'.git').exists()) for p in self.items]

    def get(self,key):
        with self.lock:
            row=next((p for p in self.items if p['id']==key),None)
            if not row: raise ValueError('Project is no longer registered. Select a destination again.')
            return dict(row)

    def add(self,payload):
        raw=payload.get('path');name=payload.get('name','')
        if not isinstance(raw,str) or not raw.strip() or len(raw)>2000 or not isinstance(name,str) or len(name)>80: raise ValueError('Enter a repository path and a name of up to 80 characters.')
        path=Path(raw.strip()).expanduser().resolve()
        if not path.is_dir() or not (path/'.git').exists(): raise ValueError('Choose the root of an existing Git repository, containing .git.')
        for agent in ('codex','claude'): project_destination(path,agent)
        with self.lock:
            if any(p['path']==str(path) for p in self.items): raise ValueError('This repository is already onboarded.')
            if len(self.items)>=50: raise ValueError('Up to 50 projects can be onboarded.')
            row=dict(id=secrets.token_hex(12),name=name.strip() or path.name,path=str(path))
            self.items.append(row);self.save();return row

    def remove(self,key):
        with self.lock:
            self.get(key);self.items=[p for p in self.items if p['id']!=key];self.save()
        return {'removed':True}

    def roots(self):
        result=[]
        for row in self.listing():
            if not row['available']: continue
            for agent in ('codex','claude'):
                try: result.append(project_destination(row['path'],agent))
                except ValueError: pass
        return result

    def scope(self,library):
        for row in self.listing():
            if Path(library).resolve() in [(Path(row['path'])/'.agents/skills').resolve(),(Path(row['path'])/'.claude/skills').resolve()]: return row['id']
        return ''

    def notes(self,payload):
        key=payload.get('id');value=payload.get('notes')
        notes=value if isinstance(value,dict) else {payload.get('agent'):value}
        if not notes or any(agent not in ('codex','claude') or not isinstance(text,str) or len(text)>2000 for agent,text in notes.items()):raise ValueError('Enter up to 2,000 characters for each agent’s project notes.')
        with self.lock:
            self.get(key);row=next(p for p in self.items if p['id']==key)
            row.setdefault('notes',{}).update({agent:text.strip() for agent,text in notes.items()});self.save();return dict(row)
