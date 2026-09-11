"""Local tester feedback, recommendation choices and installation history."""
import hashlib
import json
from pathlib import Path
import platform
import secrets
import stat
import threading
import time

VERSION='0.3.0'

def bounded(value,limit,label,empty=True):
    if not isinstance(value,str) or len(value)>limit or (not empty and not value.strip()): raise ValueError('Invalid '+label+'.')
    return value.strip()

class Experience:
    def __init__(self,state):
        self.path=Path(state)/'experience.json';self.lock=threading.RLock()
        try:
            value=json.loads(self.path.read_text(encoding='utf-8'))
            self.data=value if isinstance(value,dict) else {}
        except (ValueError,OSError):self.data={}
        for key in ('choices','installations'):
            if not isinstance(self.data.get(key),list):self.data[key]=[]
    def save(self):
        self.path.parent.mkdir(parents=True,exist_ok=True)
        tmp=self.path.with_suffix('.tmp');tmp.write_text(json.dumps(self.data,indent=2),encoding='utf-8');tmp.replace(self.path)
    def choices(self,agent,project=''):
        with self.lock:return [dict(x) for x in self.data['choices'] if x['agent']==agent and x['project']==project]
    def choose(self,payload,skill,project=''):
        agent=payload.get('agent');status=payload.get('status')
        if agent not in ('codex','claude') or status not in ('saved','dismissed','reset'):raise ValueError('Choose a valid agent and recommendation action.')
        note=bounded(payload.get('note',''),500,'recommendation note')
        with self.lock:
            old=self.data['choices'];keep=[x for x in old if (x['skill'],x['agent'],x['project'])!=(skill['id'],agent,project)]
            if status!='reset':
                if len(keep)>=1000:raise ValueError('Clear some saved or dismissed suggestions first.')
                keep.append(dict(skill=skill['id'],name=skill['name'],collection=skill['collection'],agent=agent,project=project,status=status,note=note,reason=bounded(payload.get('reason',''),1200,'reason'),firstStep=bounded(payload.get('firstStep',''),1500,'first step'),updated=time.time()))
            self.data['choices']=keep;self.save()
        return self.choices(agent,project)
    def record_install(self,record):
        with self.lock:
            row=dict(record,id=secrets.token_hex(16),installed_at=time.time(),status='installed',rating='',ratingNote='')
            self.data['installations'].append(row)
            try:self.save()
            except Exception:self.data['installations'].pop();raise
            return row
    def history(self):
        with self.lock:return [dict(x) for x in reversed(self.data['installations'])]
    def get_install(self,key):
        with self.lock:
            row=next((x for x in self.data['installations'] if x['id']==key),None)
            if not row:raise ValueError('Installation record not found.')
            return dict(row)
    def update_install(self,key,**changes):
        with self.lock:
            row=next((x for x in self.data['installations'] if x['id']==key),None)
            if not row:raise ValueError('Installation record not found.')
            previous=dict(row);row.update(changes)
            try:self.save()
            except Exception:row.clear();row.update(previous);raise
            return dict(row)
    def rate(self,payload):
        rating=payload.get('rating')
        if rating not in ('useful','confusing','unused',''):raise ValueError('Choose useful, confusing, or unused.')
        return self.update_install(payload.get('id'),rating=rating,ratingNote=bounded(payload.get('note',''),1000,'rating note'),rated_at=time.time())

def tree_digest(folder):
    """Hash file names and bytes; links or unreadable trees cannot be safely undone."""
    folder=Path(folder)
    if not folder.is_dir() or folder.is_symlink():raise ValueError('The installed skill is missing or linked. Manage it in its library.')
    digest=hashlib.sha256();total=0
    for item in sorted(folder.rglob('*')):
        if item.is_symlink():raise ValueError('The skill contains links. Its files will be preserved.')
        digest.update(item.relative_to(folder).as_posix().encode());digest.update(str(stat.S_IMODE(item.stat().st_mode)).encode());digest.update(b'\0')
        if item.is_file():
            size=item.stat().st_size;total+=size
            if total>100_000_000:raise ValueError('The skill is too large to verify for undo.')
            digest.update(item.relative_to(folder).as_posix().encode());digest.update(b'\0');digest.update(item.read_bytes());digest.update(b'\0')
    return digest.hexdigest()

def feedback_preview(payload):
    kind=payload.get('kind')
    if kind not in ('Bug','Idea','Confusing experience'):raise ValueError('Choose a feedback type.')
    title=bounded(payload.get('title'),120,'feedback title',False)
    message=bounded(payload.get('message'),5000,'feedback details',False)
    context=bounded(payload.get('screen',''),80,'screen')
    details=f'## {kind}\n\n{message}\n\n## App details\n\n- Skill-Desk: {VERSION}\n- OS: {platform.system()} {platform.release()}\n- Screen: {context or "Not specified"}\n'
    return dict(title=f'[{kind}] {title}',body=details)
