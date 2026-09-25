"""Whole-folder draft revisions and reviewed supporting-file changes."""
import difflib
from pathlib import Path
import re
import shutil
import tempfile
import time
import uuid
from experience import tree_digest


def file_diff(before, after, name):
    try:
        a=(before or b'').decode('utf-8'); b=(after or b'').decode('utf-8')
        if '\x00' in a+b: raise UnicodeError()
        diff='\n'.join(difflib.unified_diff(a.splitlines(),b.splitlines(),fromfile='Previous/'+name,tofile='Proposed/'+name,lineterm=''))
        return dict(file=name,diff=diff[:100000],truncated=len(diff)>100000,binary=False)
    except UnicodeError: return dict(file=name,binary=True,diff='Binary contents changed; text comparison is unavailable.')


class AdvancedDrafts:
    def remember_tree(self, draft, candidate, folder):
        history=draft.setdefault('treeRevisions',{}).setdefault(candidate,[])
        size=sum(p.stat().st_size for p in folder.rglob('*') if p.is_file())
        if size>30_000_000: raise ValueError('Draft is too large for revision history.')
        base=Path(self.temporary.name)/('revision-'+uuid.uuid4().hex)
        shutil.copytree(folder,base)
        history.append(dict(path=str(base),at=time.time(),digest=tree_digest(base)))
        while len(history)>10:
            shutil.rmtree(history.pop(0)['path'],ignore_errors=True)

    def folder_revisions(self,data):
        draft,folder=self.draft_candidate(data)
        return dict(current=tree_digest(folder),revisions=[dict(index=i,at=r['at'],digest=r['digest']) for i,r in enumerate(draft.get('treeRevisions',{}).get(data['candidate'],[]))])

    def restore_revision(self,data):
        with self.lock:
            draft,folder=self.draft_candidate(data)
            if tree_digest(folder)!=data.get('expected'): raise ValueError('Draft changed. Review its revisions again.')
            rows=draft.get('treeRevisions',{}).get(data['candidate'],[])
            index=data.get('index')
            if not isinstance(index,int) or not 0<=index<len(rows): raise ValueError('Choose an existing revision.')
            source=Path(rows[index]['path'])
            if tree_digest(source)!=rows[index]['digest']: raise ValueError('Revision failed verification.')
            return self.fork_folder(draft,source,candidate=data['candidate'])

    def fork_folder(self,draft,folder,target_root=None,target_agent=None,candidate="0"):
        result=self.stage([folder],draft['kind'],draft['source'],target_root or draft.get('target_root'),[target_root] if target_root else draft.get('conflict_roots'))
        new=self.drafts[result['draft']]
        for key in ('project_path','target_agent','presentation','updateExpected'):
            if key in draft and target_root is None:new[key]=draft[key]
        if target_agent:new['target_agent']=target_agent
        for key in ('upstream','baselines'):
            if candidate in draft.get(key,{}):new[key]={'0':draft[key][candidate]}
        for previous in draft.get('treeRevisions',{}).get(candidate,[]):self.remember_tree(new,'0',Path(previous['path']))
        return self.describe_draft(result['draft'])

    def file_changes(self,data):
        """Create a new validated preview. The original draft survives every error."""
        from management import inventory,validate_folder
        from skill_packages import portable_path
        with self.lock:
            draft,folder=self.draft_candidate(data)
            expected=tree_digest(folder)
            if data.get('expected')!=expected: raise ValueError('Draft changed. Reopen its file editor.')
            changes=data.get('changes')
            if not isinstance(changes,list) or not 1<=len(changes)<=1000: raise ValueError('Choose between 1 and 1,000 file changes.')
            with tempfile.TemporaryDirectory(prefix='skilldesk-files-') as work:
                copy=Path(work)/'skill';shutil.copytree(folder,copy)
                files=set(inventory(copy))
                for change in changes:
                    name=change.get('file','');portable_path(name)
                    if name.split('/')[0] in {'.git','.skilldesk'}: raise ValueError('Reserved draft path.')
                    path=copy/name; action=change.get('action')
                    if action in {'edit','remove','rename'} and name not in files: raise ValueError('File no longer exists: '+name)
                    if action=='rename':
                        target=change.get('to','');portable_path(target)
                        if name=='SKILL.md' or target=='SKILL.md': raise ValueError('Keep the SKILL.md entrypoint in place.')
                        if (copy/target).exists(): raise ValueError('Rename destination already exists.')
                        (copy/target).parent.mkdir(parents=True,exist_ok=True)
                        path.rename(copy/target);files.remove(name);files.add(target)
                    elif action=='remove':
                        if name=='SKILL.md': raise ValueError('The draft needs SKILL.md.')
                        path.unlink();files.remove(name)
                    elif action in {'edit','add'}:
                        text=change.get('content')
                        if not isinstance(text,str) or len(text.encode())>200000 or '\x00' in text: raise ValueError('Use UTF-8 text up to 200 KB.')
                        if action=='add' and path.exists(): raise ValueError('File already exists.')
                        path.parent.mkdir(parents=True,exist_ok=True);path.write_text(text,encoding='utf-8');files.add(name)
                    else: raise ValueError('Unknown file change.')
                info=validate_folder(copy)
                if tree_digest(folder)!=expected: raise ValueError('Draft changed during editing.')
                diffs=[]
                for name in sorted(set(inventory(folder))|set(info['files'])):
                    a=(folder/name).read_bytes() if (folder/name).is_file() else None
                    b=(copy/name).read_bytes() if (copy/name).is_file() else None
                    if a!=b: diffs.append(file_diff(a,b,name))
                result=self.fork_folder(draft,copy,candidate=data['candidate'])
                new=self.drafts[result['draft']]
                # Keep a complete previous folder, including supporting files.
                self.remember_tree(new,'0',folder)
                result['fileChanges']=diffs
                return result

    def replace_text(self,data):
        from management import inventory
        _,folder=self.draft_candidate(data)
        find,replacement=data.get('find'),data.get('replacement')
        if not isinstance(find,str) or not find or len(find)>10000 or not isinstance(replacement,str) or len(replacement)>10000: raise ValueError('Enter bounded search and replacement text.')
        changes=[]
        for name in inventory(folder):
            path=folder/name
            if path.stat().st_size>200000: continue
            try:text=path.read_text(encoding='utf-8')
            except UnicodeError:continue
            if '\x00' not in text and find in text:changes.append(dict(action='edit',file=name,content=text.replace(find,replacement)))
        if not changes: raise ValueError('No matching text in editable files.')
        return self.file_changes(dict(data,changes=changes))

    def export_draft(self,data):
        from skill_packages import export_package
        _,folder=self.draft_candidate(data)
        return export_package([dict(folder=folder)])
