"""Local organization, bounded search and explainable checks without model calls."""
from collections import defaultdict
import difflib
import hashlib
import json
from pathlib import Path
import re
import time
import unicodedata
import yaml
from durable_state import StateFile
from job_control import checkpoint


class LibraryTools:
    def __init__(self,state):
        self.store=StateFile(Path(state)/'organization.json',{})
        self.data=self.store.value
        for key in ('skills','searches','collections'):self.data.setdefault(key,{})

    def annotate(self,folder,payload):
        value=dict(self.data['skills'].get(str(folder),{}))
        for key,limit in (('notes',10000),):
            if key in payload:
                if not isinstance(payload[key],str) or len(payload[key])>limit:raise ValueError('Notes must be at most 10,000 characters.')
                value[key]=payload[key]
        for key in ('tags','collections'):
            if key in payload:
                items=payload[key]
                if not isinstance(items,list) or len(items)>30 or any(not isinstance(v,str) or not 1<=len(v.strip())<=80 for v in items):raise ValueError('Use at most 30 labels of 1 to 80 characters.')
                value[key]=sorted(set(v.strip() for v in items))
        if 'favorite' in payload:
            if not isinstance(payload['favorite'],bool):raise ValueError('Invalid favorite value.')
            value['favorite']=payload['favorite']
        value['updated']=time.time()
        self.data['skills'][str(folder)]=value;self.store.save(self.data)
        return value

    def saved_search(self,payload):
        name=payload.get('name');query=payload.get('query')
        if not isinstance(name,str) or not 1<=len(name.strip())<=80:raise ValueError('Name the search using 1 to 80 characters.')
        if payload.get('delete'):self.data['searches'].pop(name,None)
        else:
            if not isinstance(query,dict) or len(json.dumps(query))>5000:raise ValueError('Invalid search.')
            if len(self.data['searches'])>=100 and name not in self.data['searches']:raise ValueError('Delete a saved search before adding another.')
            self.data['searches'][name]=query
        self.store.save(self.data);return self.data['searches']

    def search(self,entries,query,registry):
        words=str(query.get('text','')).casefold().split();rows=[];read=0
        for entry in entries[:2000]:
            checkpoint();folder=Path(entry['folder']);origin=registry.get(str(folder),{})
            extra=dict(self.data['skills'].get(str(folder),{}))
            extra['favorite']=entry.get('favorite',extra.get('favorite',False))
            if query.get('agent') and query['agent'] not in entry.get('harnesses',[]):continue
            if query.get('project') and query['project']!=entry.get('project'):continue
            if query.get('origin') and query['origin']!=origin.get('kind','Existing'):continue
            if query.get('tag') and query['tag'] not in extra.get('tags',[]):continue
            if query.get('collection') and query['collection'] not in extra.get('collections',[]):continue
            if query.get('favorite') and not extra.get('favorite'):continue
            try:
                path=folder/'SKILL.md';size=path.stat().st_size
                if size>200000 or read+size>32_000_000:continue
                text=path.read_text(encoding='utf-8');read+=size
                if query.get('modifiedAfter') and path.stat().st_mtime<float(query['modifiedAfter']):continue
            except (OSError,UnicodeError):continue
            haystack=(entry['name']+' '+text+' '+extra.get('notes','')+' '+' '.join(extra.get('tags',[]))).casefold()
            if not all(word in haystack for word in words):continue
            rows.append(dict(entry,**extra,origin=origin.get('kind','Existing'),modified=path.stat().st_mtime))
        return dict(results=rows,partial=len(entries)>2000 or read>=31_800_000,bytesRead=read,searches=self.data['searches'])

    def duplicates(self,entries):
        from upstream import bytes_map
        hashes=defaultdict(list);names=defaultdict(list)
        for row in entries[:2000]:
            checkpoint()
            try:
                files=bytes_map(Path(row['folder']));digest=hashlib.sha256()
                for name,content in sorted(files.items()):digest.update(name.encode()+b'\0'+hashlib.sha256(content).digest())
                hashes[digest.hexdigest()].append(row)
                names[row['name'].casefold()].append(row)
            except (OSError,ValueError):continue
        similar=[];representatives=[v[0] for v in names.values()]
        for i,a in enumerate(representatives[:500]):
            for b in representatives[i+1:500]:
                aw=set(re.findall(r'[a-z]{4,}',a.get('summary','').lower()));bw=set(re.findall(r'[a-z]{4,}',b.get('summary','').lower()))
                overlap=len(aw&bw)/max(1,len(aw|bw))
                if difflib.SequenceMatcher(None,a['name'],b['name']).ratio()>=.65 and overlap>=.3:
                    similar.append(dict(first=a,second=b,reason='Similar names and overlapping description words; review their purpose before removing either copy.'))
                    if len(similar)>=100:break
            if len(similar)>=100:break
        conflicts=[]
        for agent in ('codex','claude','opencode','cursor'):
            for project in {''}|{e.get('project','') for e in entries[:2000]}:
                effective=defaultdict(list)
                for entry in entries[:2000]:
                    if agent in entry.get('harnesses',[]) and (not entry.get('project') or entry['project']==project):effective[entry['name'].casefold()].append(entry)
                for name,copies in effective.items():
                    if len({str(Path(e['folder']).resolve()) for e in copies})>1 and len(conflicts)<200:conflicts.append(dict(agent=agent,project=project,name=name,locations=[e['folder'] for e in copies]))
        return dict(conflicts=conflicts,exact=[v for v in hashes.values() if len(v)>1],names=[v for v in names.values() if len(v)>1],similar=similar,partial=len(entries)>2000 or len(representatives)>500)

    def collection_coverage(self,entries):
        groups=defaultdict(list)
        for entry in entries:
            for name in self.data['skills'].get(str(entry['folder']),{}).get('collections',[]):groups[name].append(entry)
        return dict(collections=[dict(name=name,skills=rows,agents={agent:sorted({r['name'] for r in rows if agent in r.get('harnesses',[])}) for agent in ('codex','claude','opencode','cursor')}) for name,rows in sorted(groups.items())])


def quality(folder,agents=None):
    from management import validate_folder,inventory,metadata,local_references
    from skill_packages import portable_path
    folder=Path(folder);issues=[]
    def issue(code,message,severity='advisory',file='SKILL.md'):issues.append(dict(code=code,message=message,severity=severity,file=file))
    try:details=validate_folder(folder)
    except Exception as error:
        issue('invalid',str(error),'blocking');return dict(issues=issues,valid=False)
    text=details['content'];meta=metadata(text);description=meta['description']
    if len(description.split())<5 or re.search(r'\b(anything|everything|all tasks|always use)\b',description,re.I):issue('broad-description','The description may be too broad to identify a specific task. Add a concrete trigger.')
    if meta.get('disable-model-invocation') is True and details['invocation']=='Automatic or explicit' and (folder/'agents/openai.yaml').exists():issue('invocation-conflict','Explicit-only frontmatter and OpenAI automatic invocation policy disagree.')
    common={'name','description','license','compatibility','metadata','allowed-tools','disable-model-invocation','user-invocable','argument-hint','model','context','agent','hooks','icon','color','slash'}
    standard={'name','description','license','compatibility','metadata','allowed-tools'}
    supported={'codex':standard,'claude':standard|{'disable-model-invocation','user-invocable','argument-hint','model','context','agent','hooks'},'cursor':standard|{'disable-model-invocation','icon','color'},'opencode':standard|{'slash'}}
    for agent in (agents or []):
        for key in set(meta)-supported.get(agent,common):issue('agent-field',str(key)+' is not in the documented '+agent+' field set. Verify behavior before relying on it.')
    for key in meta:
        if key not in common:issue('unknown-metadata','Unrecognized frontmatter field: '+str(key)+'. Check support in the destination agent.')
    if 'opencode' in (agents or []) and meta.get('disable-model-invocation'):issue('opencode-invocation','OpenCode does not use disable-model-invocation. V2 supports metadata.opencode/autoinvoke: false; older versions need their own permission configuration.')
    names={};references=[]
    for name in inventory(folder):
        checkpoint();path=folder/name;folded=unicodedata.normalize('NFC',name).casefold()
        if folded in names:issue('case-collision','Conflicts with '+names[folded]+' on case-insensitive filesystems.','blocking',name)
        names[folded]=name
        try:portable_path(name)
        except ValueError:issue('nonportable-path','Filename is not portable to all supported platforms.','blocking',name)
        if any(part in {'node_modules','__pycache__','.venv','dist','.DS_Store'} for part in Path(name).parts):issue('generated-file','This looks like a generated or machine-specific file.',file=name)
        if path.stat().st_size>1_000_000:issue('large-file','File exceeds 1 MB. Review whether it belongs in the skill.',file=name)
        if path.suffix.lower() not in {'.md','.markdown','.txt','.yaml','.yml','.json','.sh','.py','.js','.ts','.ps1'}:continue
        if path.stat().st_size>200000:continue
        try:document=path.read_text(encoding='utf-8')
        except UnicodeError:issue('encoding','Text file is not valid UTF-8.',file=name);continue
        if re.search(r'(/Users/|/home/|[A-Z]:\\|\b(brew|apt-get|powershell|osascript)\b)',document):issue('platform-specific','Contains platform-specific commands or absolute home paths. Review portability.',file=name)
        if path.suffix.lower() in {'.md','.markdown'}:
            for reference in local_references(document):
                target=(path.parent/reference).resolve()
                if not target.is_relative_to(folder.resolve()):references.append(dict(file=name,reference=reference))
            for warning in details.get('warnings',[]):
                if ' in '+name+':' in warning:issue('reference',warning,file=name)
    return dict(valid=not any(x['severity']=='blocking' for x in issues),issues=issues,externalSkillReferences=references,agents=agents or [],checkedAt=time.time())
