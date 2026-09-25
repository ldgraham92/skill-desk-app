"""Read bounded samples of local user prompts. Never execute history content."""
from datetime import datetime, timezone
import hashlib
import json
import os
import ntpath
from pathlib import Path
import re
import sqlite3
from contextlib import closing
import time
from collections import defaultdict, deque, Counter
from job_control import checkpoint

LABELS = {'codex': 'Codex', 'claude': 'Claude Code', 'opencode': 'OpenCode'}
MAX_EXCERPTS = 120
MAX_TEXT = 1000
MAX_SCAN_BYTES = 32_000_000
MAX_FILE_BYTES = 2_000_000
MAX_SESSION_HEADER_BYTES = 256_000
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
    text = re.sub(r'(?is)<(environment_context|system-reminder|instructions|permissions instructions|user_instructions|recommended_plugins)>.*?</\1>', '', text)
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


def codex_user_text(content):
    parts=content if isinstance(content,list) else [dict(type='input_text',text=content)]
    return '\n'.join(redact(part['text']) for part in parts
        if isinstance(part,dict) and part.get('type') in {'text','input_text'}
        and isinstance(part.get('text'),str)
        and not part['text'].lstrip().startswith('# AGENTS.md instructions for'))


def jsonl_records(data):
    result=[]
    for line in data.splitlines():
        if len(line)>250_000: continue
        try:
            obj=json.loads(line)
            if isinstance(obj,dict): result.append(obj)
        except (ValueError,UnicodeDecodeError): continue
    return result


def subagent_session(records):
    for row in records:
        payload=row.get('payload')
        if row.get('type')!='session_meta' or not isinstance(payload,dict): continue
        source=payload.get('source')
        if source=='subagent' or (isinstance(source,dict) and 'subagent' in source): return True
    return False


def project_matches(cwd, project_path):
    """Compare absolute directory metadata, never project names or prompt text."""
    if not isinstance(cwd, str) or not cwd or not isinstance(project_path, str): return False
    if os.name!='nt' and ntpath.isabs(project_path) and ntpath.splitdrive(project_path)[0]:
        if not ntpath.isabs(cwd) or not ntpath.splitdrive(cwd)[0]: return False
        root, directory = ntpath.normcase(ntpath.normpath(project_path)), ntpath.normcase(ntpath.normpath(cwd))
        try: return ntpath.commonpath([root, directory]) == root
        except ValueError: return False
    if not Path(cwd).is_absolute() or not Path(project_path).is_absolute(): return False
    try:
        root, directory = Path(project_path).resolve(), Path(cwd).resolve()
        if not directory.is_relative_to(root): return False
        # A nested repository belongs to its own project.
        for parent in (directory, *directory.parents):
            if parent == root: return True
            if (parent/'.git').exists(): return False
    except (OSError, RuntimeError): pass
    return False


def representative(rows, limit):
    """Round-robin across source/project/day buckets, newest in each bucket first."""
    buckets=defaultdict(deque)
    for row in sorted(rows,key=lambda r:r['timestamp'],reverse=True):
        day=datetime.fromtimestamp(row['timestamp'],timezone.utc).strftime('%Y-%m-%d')
        buckets[(row['source'],row.get('_projectKey',''),day,row.get('_session',''))].append(row)
    result=[]
    while buckets and len(result)<limit:
        for key in list(buckets):
            result.append(buckets[key].popleft())
            if not buckets[key]: del buckets[key]
            if len(result)>=limit: break
    return result


def scan(selected, days=30, locations=None, now=None, project_path=None, deep=False, registered_projects=None, exclusions=None):
    if not isinstance(selected, list) or not selected or len(selected)>3 or any(not isinstance(x,str) or x not in LABELS for x in selected) or len(set(selected))!=len(selected):
        raise ValueError('Choose one or more supported history sources.')
    if type(days) is not int or days not in {7, 30, 90}: raise ValueError('Choose 7, 30 or 90 days.')
    locations, now = locations or roots(), now or time.time()
    scan_limit=MAX_SCAN_BYTES*4 if deep else MAX_SCAN_BYTES
    file_limit=MAX_FILE_BYTES*2 if deep else MAX_FILE_BYTES
    cutoff, remaining, file_count = now-days*86400, scan_limit, 0
    project_cache={}
    rows, notes, seen = [], [], {}
    coverage={source:dict(sessionsFound=0,sessionsScanned=0,sessionsSkipped=0,subagentSessions=0,budgetSkippedSessions=0,sessionsIncluded=0,sessionsWithPrompts=0,
        filesRead=0,unreadableFiles=0,unreadableDirectories=0,malformedRecords=0,truncatedFiles=0,duplicates=0,
        bytesRead=0,changedFiles=0,excludedPrompts=0,timeExcluded=0,scopeExcluded=0,instructionExcluded=0,status='missing') for source in selected}
    current_file=None
    included_files=set()
    eligible=0
    def project_info(cwd):
        if not isinstance(cwd,str) or not cwd: return '',None
        if cwd in project_cache: return project_cache[cwd]
        matches=[p for p in (registered_projects or []) if project_matches(cwd,p['path'])]
        if matches:
            project=max(matches,key=lambda p:len(p['path']))
            result=(hashlib.sha256(project['path'].encode()).hexdigest(),redact(project['name'])[:100])
            project_cache[cwd]=result;return result
        path=ntpath.normpath(cwd) if ntpath.splitdrive(cwd)[0] else os.path.normpath(cwd)
        label=ntpath.basename(path) if ntpath.splitdrive(path)[0] else Path(path).name
        return hashlib.sha256(path.encode()).hexdigest(),redact(label)[:100] or 'Unnamed project'
    if project_path is not None and (not isinstance(project_path,str) or not project_path):
        raise ValueError('Choose a repository for project-only history.')
    if project_path is not None and any(s not in {'codex','claude','opencode'} for s in selected):
        raise ValueError('Project-only history is not supported for this source.')
    excluded_unknown = 0

    def add(source, value, text, cwd=None):
        nonlocal excluded_unknown, eligible
        checkpoint()
        when = timestamp(value)
        if not cutoff<=when<=now+300 or not isinstance(text, str):
            coverage[source]['timeExcluded']+=1
            return
        if any(project_matches(cwd,path) for path in (exclusions or {}).get('projects',[])):
            coverage[source]['excludedPrompts']+=1
            return
        if project_path is not None and not project_matches(cwd, project_path):
            coverage[source]['scopeExcluded']+=1
            if not isinstance(cwd,str) or not cwd: excluded_unknown += 1
            return
        text = redact(text)
        if len(text)<12 or text.startswith(('<environment_context>', '<turn_aborted>', '<local-command-', '<command-name>')):
            coverage[source]['instructionExcluded']+=1
            return
        project_key,project=project_info(cwd)
        day=datetime.fromtimestamp(when,timezone.utc).strftime('%Y-%m-%d')
        key = (source, text, day)
        previous=seen.get(key)
        if previous is not None and (not previous['_projectKey'] or not project_key or previous['_projectKey']==project_key):
            coverage[source]['duplicates']+=1
            if project_key and not previous['_projectKey']:
                previous.update(_projectKey=project_key,project=project,_session=current_file)
                if current_file: included_files.add((source,current_file))
            return
        row=dict(source=source,timestamp=when,text=text,_projectKey=project_key,project=project,_session=current_file)
        seen[key]=row
        rows.append(row)
        eligible+=1
        if current_file: included_files.add((source,current_file))
        if len(rows)>3000: rows[:]=representative(rows,2500)
        # Bound duplicate metadata too. Losing old keys only affects deduplication,
        # never the scan's memory budget or the selected destination.
        if len(seen)>6000: seen.clear()

    def files(base, pattern):
        nonlocal file_count
        found=[]
        if not base.is_dir(): return found
        # Do not follow directory symlinks or traverse a whole home directory.
        def directory_error(error):
            coverage[source]['unreadableDirectories']+=1
            notes.append('Some history directories could not be read. Check access permissions and try again.')
        for folder, dirs, names in os.walk(base, followlinks=False,onerror=directory_error):
            checkpoint()
            file_count+=1
            if file_count>MAX_FILES:
                notes.append('File scan limit reached; this is a partial sample.')
                break
            dirs[:] = sorted((d for d in dirs if not d.startswith('.') and d not in {'subagents','node_modules'}),reverse=True)
            for name in names:
                if not name.endswith(pattern): continue
                p=Path(folder)/name
                if p.is_symlink(): continue
                try: modified=p.stat().st_mtime
                except OSError:
                    coverage[source]['unreadableFiles']+=1
                    notes.append('Some history files could not be read. Check access permissions and try again.')
                    continue
                file_count+=1
                if file_count>MAX_FILES:
                    notes.append('File scan limit reached; this is a partial sample.')
                    return sorted(found, key=lambda p:p[0], reverse=True)
                found.append((modified,p))
        return sorted(found, key=lambda p:p[0], reverse=True)

    def read_jsonl(path, session_header=False, fair_limit=None):
        nonlocal remaining
        checkpoint()
        stats=coverage[source]
        is_session=path.name!='history.jsonl'
        if any(path.resolve().is_relative_to(Path(value).expanduser().resolve()) for value in (exclusions or {}).get('locations',[])):
            stats['sessionsSkipped']+=int(is_session)
            return []
        if remaining<=0 or path.is_symlink() or not path.is_file():
            if is_session: stats['sessionsSkipped']+=1
            return []
        stats['status']='read'
        try:
            size=path.stat().st_size
            take=min(size, file_limit, remaining, fair_limit if fair_limit is not None else file_limit)
            with path.open('rb') as stream:
                first=stream.readline(min(64_000,take)) if session_header else b''
                if session_header and subagent_session(jsonl_records(first)):
                    remaining-=len(first)
                    stats['bytesRead']+=len(first)
                    stats['sessionsSkipped']+=1
                    stats['subagentSessions']+=1
                    return []
                if take<size:
                    header=first+stream.read(max(0,min(MAX_SESSION_HEADER_BYTES,take//2)-len(first))) if session_header else b''
                    consumed=len(header)
                    pieces=[header.rpartition(b'\n')[0]] if header else []
                    budget=take-len(header)
                    windows=3 if session_header and take>=512_000 else 1
                    window_size=budget//windows
                    for index in range(1,windows+1):
                        checkpoint()
                        length=window_size if index<windows else budget-window_size*(windows-1)
                        offset=int(len(header)+(size-take)*index/windows+window_size*(index-1))
                        stream.seek(offset)
                        chunk=stream.read(length);consumed+=len(chunk)
                        # Both cut edges can contain partial JSON records.
                        chunk=chunk.partition(b'\n')[2]
                        if offset+length<size: chunk=chunk.rpartition(b'\n')[0]
                        pieces.extend([b'{"type":"skilldesk_scan_gap"}',chunk])
                    data=b'\n'.join(pieces)
                else:
                    data=first+stream.read(take-len(first))
                    consumed=len(data)
            if path.stat().st_size!=size:
                stats['changedFiles']+=1
                notes.append('A history file changed while it was read; this is a partial sample. Refresh to include new messages.')
            remaining-=consumed
            stats['bytesRead']+=consumed
            stats['filesRead']+=1
            if is_session: stats['sessionsScanned']+=1
            if take<size:
                stats['truncatedFiles']+=1
                notes.append('Some history files were truncated into bounded windows; this is a partial sample.')
            result=jsonl_records(data)
            stats['malformedRecords']+=sum(1 for line in data.splitlines() if line.strip())-len(result)
            if session_header and subagent_session(result):
                stats['sessionsScanned']-=1
                stats['sessionsSkipped']+=1
                stats['subagentSessions']+=1
                return []
            return result
        except OSError:
            stats['unreadableFiles']+=1
            if is_session: stats['sessionsSkipped']+=1
            notes.append('Some history files could not be read. Check access permissions and try again.')
            return []

    for source in selected:
        root=locations[source]
        if any((root/p).exists() for p in ('history.jsonl','sessions','archived_sessions','projects','opencode.db','storage/message')):
            coverage[source]['status']='empty'
        before=eligible
        current_file=None
        if source in {'codex','claude'}:
            for obj in read_jsonl(root/'history.jsonl'):
                add(source,obj.get('ts') if source=='codex' else obj.get('timestamp'), obj.get('text') if source=='codex' else obj.get('display'), obj.get('project') if source=='claude' else None)
            bases=[root/'sessions',root/'archived_sessions'] if source=='codex' else [root/'projects']
            found_files=sorted([entry for base in bases for entry in files(base,'.jsonl')],reverse=True)
            coverage[source]['sessionsFound']=len(found_files)
            for index,(_,path) in enumerate(found_files):
                    if remaining<=0:
                        coverage[source]['sessionsSkipped']+=len(found_files)-index
                        coverage[source]['budgetSkippedSessions']+=len(found_files)-index
                        break
                    current_file=str(path)
                    records=read_jsonl(path, session_header=source=='codex',fair_limit=max(4096,remaining//max(1,len(found_files)-index)))
                    cwd=None
                    for obj in records:
                        if source=='codex':
                            # A skipped turn could have changed directory. Require
                            # fresh context before attributing the tail to a repo.
                            if obj.get('type')=='skilldesk_scan_gap': cwd=None
                            payload=obj.get('payload',{})
                            if isinstance(payload,dict) and obj.get('type') in {'session_meta','turn_context'}:
                                cwd=payload.get('cwd')
                            if isinstance(payload,dict) and obj.get('type')=='event_msg' and payload.get('type')=='user_message':
                                add(source,obj.get('timestamp'),payload.get('message'),cwd)
                            elif isinstance(payload,dict) and obj.get('type')=='response_item' and payload.get('type')=='message' and payload.get('role')=='user':
                                add(source,obj.get('timestamp'),codex_user_text(payload.get('content')),cwd)
                        elif obj.get('type')=='user' and not obj.get('isMeta') and not obj.get('isSidechain'):
                            message=obj.get('message',{})
                            if isinstance(message,dict): add(source,obj.get('timestamp'),user_text(message.get('content')),obj.get('cwd'))
        else:
            database=root/'opencode.db'
            if database.is_file() and not database.is_symlink():
                try:
                    with closing(sqlite3.connect(database.resolve().as_uri()+'?mode=ro',uri=True,timeout=1)) as db:
                        db.execute('PRAGMA query_only=ON')
                        deadline=time.monotonic()+3
                        db.set_progress_handler(lambda:int(time.monotonic()>deadline),1000)
                        tables={r[0] for r in db.execute("SELECT name FROM sqlite_master WHERE type='table'")}
                        if {'session_message','session_v2'}<=tables:
                            coverage[source]['status']='read'
                            for when,data,cwd,session in db.execute("SELECT m.time_created,m.data,s.directory,s.id FROM session_message m JOIN session_v2 s ON m.session_id=s.id WHERE m.type='user' AND s.parent_id IS NULL AND m.time_created>=? AND length(m.data)<250000 ORDER BY m.time_created DESC LIMIT 1200",(cutoff*1000,)):
                                checkpoint()
                                if len(data.encode())>remaining: break
                                remaining-=len(data.encode());coverage[source]['bytesRead']+=len(data.encode())
                                try:
                                    obj=json.loads(data);current_file=session
                                    content=obj.get('text') or user_text(obj.get('parts',obj.get('content')))
                                    add(source,when,content,cwd)
                                except (ValueError,AttributeError,TypeError): continue
                        elif 'session_message' in tables:
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
        coverage[source]['sessionsWithPrompts']=sum(s==source for s,_ in included_files)
        if coverage[source]['malformedRecords']: notes.append(LABELS[source]+': some malformed or oversized history records were skipped.')
        if eligible==before:
            if coverage[source]['status']=='missing': notes.append('No local history was found for '+LABELS[source]+'.')
            else: notes.append('History exists for '+LABELS[source]+', but no eligible prompts were found in this timeframe and scope.')
    if remaining<=0: notes.append('Read limit reached; this is a partial sample.')
    if excluded_unknown: notes.append('Some prompts had no identifiable repository and were excluded from this project-only sample.')
    if project_path is not None and not rows: notes.append('No prompts matched this repository. Try a longer timeframe or explicitly choose All projects.')
    breakdown=[dict(date=day,project=project,found=count) for (day,project),count in sorted(Counter((datetime.fromtimestamp(r['timestamp'],timezone.utc).strftime('%Y-%m-%d'),r.get('project') or 'Project unknown') for r in rows).items(),reverse=True)]
    sampled=representative(rows,MAX_EXCERPTS)
    sampled.sort(key=lambda r:r['timestamp'],reverse=True)
    for source in selected: coverage[source]['sessionsIncluded']=len({r['_session'] for r in sampled if r['source']==source and r.get('_session')})
    for i,row in enumerate(sampled):
        row['id']='prompt-'+str(i+1)
        row['date']=datetime.fromtimestamp(row.pop('timestamp'),timezone.utc).strftime('%Y-%m-%d')
        row.pop('_projectKey',None)
        row.pop('_session',None)
    if eligible>len(sampled): notes.append(f'Showing {len(sampled)} of {eligible} eligible prompts found, balanced across projects and dates.')
    partial=bool(notes and any('partial sample' in n or 'skipped' in n or 'could not be read' in n for n in notes)) or eligible>len(sampled)
    return dict(excerpts=sampled,days=days,notes=list(dict.fromkeys(notes)),sampled=len(sampled),found=eligible,
        sources=selected,coverage=coverage,checkedAt=now,partial=partial,deep=deep,breakdown=breakdown,breakdownPartial=eligible>len(rows),
        limits=dict(excerpts=MAX_EXCERPTS,charactersPerExcerpt=MAX_TEXT,scanBytes=scan_limit,fileBytes=file_limit,files=MAX_FILES))
