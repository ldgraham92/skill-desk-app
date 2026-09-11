"""Read bounded samples of local user prompts. Never execute history content."""
from datetime import datetime, timezone
import hashlib
import json
import os
from pathlib import Path
import re
import sqlite3
import time

LABELS = {'codex': 'Codex', 'claude': 'Claude Code', 'opencode': 'OpenCode'}
MAX_EXCERPTS = 120
MAX_TEXT = 1000
MAX_SCAN_BYTES = 32_000_000
MAX_FILE_BYTES = 2_000_000
MAX_FILES = 1500


def roots():
    home = Path.home()
    return {'codex': Path(os.environ.get('CODEX_HOME') or home/'.codex'),
            'claude': Path(os.environ.get('CLAUDE_CONFIG_DIR') or home/'.claude'),
            'opencode': Path(os.environ.get('XDG_DATA_HOME') or home/'.local/share')/'opencode'}


def sources(locations=None):
    locations = locations or roots()
    return [dict(id=k, label=LABELS[k], available=any((locations[k]/p).exists() for p in paths)) for k, paths in {
        'codex': ['history.jsonl', 'sessions', 'archived_sessions'],
        'claude': ['history.jsonl', 'projects'],
        'opencode': ['opencode.db', 'storage/message'],
    }.items()]


def timestamp(value):
    try:
        if isinstance(value, (float, int)): return value/1000 if value>100_000_000_000 else value
        return datetime.fromisoformat(str(value).replace('Z', '+00:00')).timestamp()
    except (ValueError, TypeError, OverflowError): return 0


def redact(text):
    # Best effort; the user reviews the exact payload before analysis.
    text = re.sub(r'(?s)-----BEGIN [^-]*PRIVATE KEY-----.*?-----END [^-]*PRIVATE KEY-----', '[private key removed]', text)
    text = re.sub(r'(?is)<(environment_context|system-reminder|instructions|permissions instructions|user_instructions)>.*?</\1>', '', text)
    text = re.sub(r'\b(?:sk-[A-Za-z0-9_-]{12,}|gh[pousr]_[A-Za-z0-9_]{15,}|github_pat_[A-Za-z0-9_]+|glpat-[A-Za-z0-9_-]+|eyJ[A-Za-z0-9_-]+\.[A-Za-z0-9_-]+\.[A-Za-z0-9_-]+)\b', '[token removed]', text)
    text = re.sub(r'(?i)\b(api[_-]?key|access[_-]?token|secret|password|authorization)\s*[:=]\s*["\']?[^\s,"\'}]+', r'\1=[removed]', text)
    text = re.sub(r'\b[\w.+-]+@[\w.-]+\.[A-Za-z]{2,}\b', '[email removed]', text)
    text = re.sub(r'(?:[A-Za-z]:[\\/]|/(?:Users|home)/)[^\s<>"\']+', '[local path]', text)
    text = re.sub(r'(?m)^# (?:AGENTS\.md|Instructions for).*$', '', text)
    return text.strip()[:MAX_TEXT]


def user_text(content):
    if isinstance(content, str): return content
    if isinstance(content, list):
        return '\n'.join(p.get('text', '') for p in content if isinstance(p, dict) and p.get('type') in {'text', 'input_text'} and isinstance(p.get('text'), str))
    return ''


def scan(selected, days=30, locations=None, now=None):
    if not isinstance(selected, list) or not selected or len(selected)>3 or any(not isinstance(x,str) or x not in LABELS for x in selected) or len(set(selected))!=len(selected):
        raise ValueError('Choose one or more supported history sources.')
    if type(days) is not int or days not in {7, 30, 90}: raise ValueError('Choose 7, 30 or 90 days.')
    locations, now = locations or roots(), now or time.time()
    cutoff, remaining, file_count = now-days*86400, MAX_SCAN_BYTES, 0
    rows, notes, seen = [], [], set()

    def add(source, value, text):
        when = timestamp(value)
        if not cutoff<=when<=now+300 or not isinstance(text, str): return
        text = redact(text)
        if len(text)<12 or text.startswith(('<environment_context>', '<turn_aborted>', '<local-command-', '<command-name>')): return
        key = (source, text)
        if key in seen: return
        seen.add(key)
        rows.append(dict(source=source, timestamp=when, text=text))
        if len(rows)>3000: rows.sort(key=lambda r:r['timestamp'],reverse=True); del rows[3000:]

    def files(base, pattern):
        nonlocal file_count
        found=[]
        if not base.is_dir(): return found
        # Do not follow directory symlinks or traverse a whole home directory.
        for folder, dirs, names in os.walk(base, followlinks=False):
            file_count+=1
            if file_count>MAX_FILES:
                notes.append('File scan limit reached; this is a partial sample.')
                break
            dirs[:] = sorted(d for d in dirs if not d.startswith('.') and d not in {'subagents','node_modules'})
            for name in names:
                if not name.endswith(pattern): continue
                p=Path(folder)/name
                if p.is_symlink(): continue
                try: modified=p.stat().st_mtime
                except OSError: continue
                file_count+=1
                if file_count>MAX_FILES:
                    notes.append('File scan limit reached; this is a partial sample.')
                    return sorted(found, key=lambda p:p[0], reverse=True)
                if modified>=cutoff: found.append((modified,p))
        return sorted(found, key=lambda p:p[0], reverse=True)

    def read_jsonl(path):
        nonlocal remaining
        if remaining<=0 or path.is_symlink() or not path.is_file(): return []
        try:
            size=path.stat().st_size
            take=min(size, MAX_FILE_BYTES, remaining)
            with path.open('rb') as stream:
                stream.seek(max(0,size-take));data=stream.read(take)
            remaining-=len(data)
            if take<size: data=data.partition(b'\n')[2]
            result=[]
            for line in data.splitlines():
                if len(line)>250_000: continue
                try:
                    obj=json.loads(line)
                    if isinstance(obj,dict): result.append(obj)
                except (ValueError,UnicodeDecodeError): continue
            return result
        except OSError:
            notes.append('Some history files could not be read.')
            return []

    for source in selected:
        root=locations[source]
        before=len(rows)
        if source in {'codex','claude'}:
            for obj in read_jsonl(root/'history.jsonl'):
                add(source,obj.get('ts') if source=='codex' else obj.get('timestamp'), obj.get('text') if source=='codex' else obj.get('display'))
            bases=[root/'sessions',root/'archived_sessions'] if source=='codex' else [root/'projects']
            for base in bases:
                for _,path in files(base,'.jsonl'):
                    if remaining<=0: break
                    for obj in read_jsonl(path):
                        if source=='codex':
                            payload=obj.get('payload',{})
                            if isinstance(payload,dict) and obj.get('type')=='event_msg' and payload.get('type')=='user_message':
                                add(source,obj.get('timestamp'),payload.get('message'))
                        elif obj.get('type')=='user' and not obj.get('isMeta') and not obj.get('isSidechain'):
                            message=obj.get('message',{})
                            if isinstance(message,dict): add(source,obj.get('timestamp'),user_text(message.get('content')))
        else:
            database=root/'opencode.db'
            if database.is_file() and not database.is_symlink():
                try:
                    with sqlite3.connect(database.resolve().as_uri()+'?mode=ro',uri=True,timeout=1) as db:
                        db.execute('PRAGMA query_only=ON')
                        deadline=time.monotonic()+3
                        db.set_progress_handler(lambda:int(time.monotonic()>deadline),1000)
                        tables={r[0] for r in db.execute("SELECT name FROM sqlite_master WHERE type='table'")}
                        if 'session_message' in tables:
                            for when,data in db.execute("SELECT time_created, data FROM session_message WHERE type='user' AND time_created>=? AND length(data)<250000 ORDER BY time_created DESC LIMIT 400",(cutoff*1000,)):
                                try: add(source,when,json.loads(data).get('text'))
                                except (ValueError,AttributeError): continue
                        if {'message','part'}<=tables:
                            for when,message,part in db.execute('SELECT m.time_created,m.data,p.data FROM message m JOIN part p ON p.message_id=m.id WHERE m.time_created>=? AND length(m.data)<250000 AND length(p.data)<250000 ORDER BY m.time_created DESC LIMIT 1200',(cutoff*1000,)):
                                try:
                                    m,p=json.loads(message),json.loads(part)
                                    if m.get('role')=='user' and p.get('type')=='text' and not p.get('synthetic') and not p.get('ignored'): add(source,when,p.get('text'))
                                except (ValueError,AttributeError): continue
                        if not ({'message','part'}<=tables or 'session_message' in tables): notes.append('OpenCode database format is not supported by this version.')
                except (sqlite3.Error,OSError): notes.append('OpenCode database was unavailable or used an unsupported format.')
            # Earlier OpenCode versions store each message and part as JSON.
            for _,path in files(root/'storage/message','.json'):
                try:
                    if remaining<=0: break
                    size=path.stat().st_size
                    if size>100_000 or size>remaining: continue
                    remaining-=size
                    obj=json.loads(path.read_text(encoding='utf-8'))
                    if obj.get('role')!='user': continue
                    message_id=obj.get('id','')
                    if not re.fullmatch(r'[A-Za-z0-9_-]+',message_id): continue
                    for _,part_path in files(root/'storage/part'/message_id,'.json'):
                        size=part_path.stat().st_size
                        if size>100_000 or size>remaining: continue
                        remaining-=size
                        p=json.loads(part_path.read_text(encoding='utf-8'))
                        if p.get('type')=='text' and not p.get('synthetic') and not p.get('ignored'): add(source,obj.get('time',{}).get('created'),p.get('text'))
                except (OSError,ValueError,AttributeError,TypeError): continue
        if len(rows)==before: notes.append('No recent user prompts found for '+LABELS[source]+'.')
    if remaining<=0: notes.append('Read limit reached; this is a partial sample.')
    # Share the sample between selected sources so a busy source cannot crowd out another.
    quota=MAX_EXCERPTS//len(selected)
    sampled=[]
    for source in selected:
        sampled.extend(sorted((r for r in rows if r['source']==source),key=lambda r:r['timestamp'],reverse=True)[:quota])
    sampled.sort(key=lambda r:r['timestamp'],reverse=True)
    for i,row in enumerate(sampled): row['id']='prompt-'+str(i+1);row['date']=datetime.fromtimestamp(row.pop('timestamp'),timezone.utc).strftime('%Y-%m-%d')
    return dict(excerpts=sampled,days=days,notes=list(dict.fromkeys(notes)),sampled=len(sampled),found=len(rows),sources=selected)
