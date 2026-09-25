"""Explicit GitHub checks and three-way file review; repository content is never run."""
import hashlib
import json
import os
from pathlib import Path
import re
import shutil
import tempfile
import uuid
from advanced_drafts import file_diff
from durable_state import atomic_json
from experience import tree_digest
from job_control import checkpoint, run_process
from platform_support import subprocess_options


def checkout(repo, ref, destination, progress=None):
    if not isinstance(repo,str) or not re.fullmatch(r'https://github\.com/[A-Za-z0-9_.-]+/[A-Za-z0-9_.-]+',repo): raise ValueError('Only recorded GitHub HTTPS sources can be updated.')
    if not isinstance(ref,str) or len(ref)>200 or ref.startswith('-') or any(c.isspace() for c in ref): raise ValueError('Invalid revision. Choose a branch, tag, or commit.')
    env=dict(os.environ,GIT_TERMINAL_PROMPT='0',GIT_LFS_SKIP_SMUDGE='1')
    commands=[['git','-c','core.hooksPath=/dev/null','clone','--no-checkout','--depth','1','--',repo+'.git',str(destination)]]
    if ref:commands.append(['git','-C',str(destination),'-c','core.hooksPath=/dev/null','fetch','--depth','1','origin',ref])
    commands.append(['git','-C',str(destination),'-c','core.hooksPath=/dev/null','checkout','--detach','FETCH_HEAD' if ref else 'HEAD'])
    for command in commands:
        checkpoint()
        result=run_process(command,capture_output=True,text=True,encoding='utf-8',timeout=180,env=env,**subprocess_options())
        if result.returncode:raise ValueError('Upstream is unavailable or the revision does not exist. Installed files are unchanged. '+result.stderr[-500:])
    return run_process(['git','-C',str(destination),'rev-parse','HEAD'],capture_output=True,text=True,encoding='utf-8',timeout=10,**subprocess_options()).stdout.strip()


def bytes_map(folder):
    from management import inventory
    return {name:(folder/name).read_bytes() for name in inventory(folder)}


def merge_files(base, local, upstream):
    """Resolve unchanged sides and non-overlapping text edits; keep conflicts explicit."""
    merged={};conflicts=[];changes=[]
    for name in sorted(set(base)|set(local)|set(upstream)):
        a,b,c=base.get(name),local.get(name),upstream.get(name)
        conflict=False
        if b==c:chosen=b
        elif b==a:chosen=c
        elif c==a:chosen=b
        elif a is not None and b is not None and c is not None and max(map(len,(a,b,c)))<=200000 and all(b'\0' not in x for x in (a,b,c)):
            try:
                for value in (a,b,c):value.decode('utf-8')
                with tempfile.TemporaryDirectory(prefix='skilldesk-merge-') as work:
                    paths=[Path(work)/str(i) for i in range(3)]
                    for path,value in zip(paths,(b,a,c)):path.write_bytes(value)
                    result=run_process(['git','merge-file','-p',*[str(p) for p in paths]],capture_output=True,timeout=10,**subprocess_options())
                    if result.returncode==0:chosen=result.stdout
                    else:conflict=True;chosen=b
            except UnicodeError:conflict=True;chosen=b
        else:conflict=True;chosen=b
        if chosen is not None:merged[name]=chosen
        if conflict:conflicts.append(dict(file=name,localDeleted=b is None,upstreamDeleted=c is None,**{k:v for k,v in file_diff(b,c,name).items() if k!='file'}))
        if b!=c:changes.append(dict(file=name,action='added' if b is None else 'removed' if c is None else 'changed',**{k:v for k,v in file_diff(b,c,name).items() if k!='file'}))
    removed={n:hashlib.sha256(v).hexdigest() for n,v in base.items() if n not in upstream}
    added={n:hashlib.sha256(v).hexdigest() for n,v in upstream.items() if n not in base}
    renames=[dict(previous=a,current=b) for a,digest in removed.items() for b,other in added.items() if digest==other]
    return merged,conflicts,changes,renames


class Upstream:
    def __init__(self,manager):self.manager=manager;self.previews={}

    def bootstrap(self,folder,progress=None):
        """Recover the recorded original revision for imports made before baselines existed."""
        from management import metadata,validate_folder
        folder=Path(folder);manager=self.manager
        record=dict(manager.registry.get(str(folder),{}))
        match=re.fullmatch(r'(https://github\.com/[A-Za-z0-9_.-]+/[A-Za-z0-9_.-]+)@([a-f0-9]{40})(?::(.*))?',record.get('source',''))
        if not match:raise ValueError('The original repository and exact commit were not recorded. Import that revision to establish its baseline.')
        expected=tree_digest(folder);name=metadata((folder/'SKILL.md').read_text())['name']
        repo,commit,path=match.groups();path=path or ''
        if progress:progress('downloading','Reading the original imported revision')
        with tempfile.TemporaryDirectory(prefix='skilldesk-baseline-') as work:
            root=Path(work)/'repo';resolved=checkout(repo,commit,root)
            selected=root/path
            if not selected.resolve().is_relative_to(root.resolve()):raise ValueError('Recorded folder is outside its repository.')
            matches=[]
            for file in selected.rglob('SKILL.md'):
                if '.git' in file.parts:continue
                try:
                    if metadata(file.read_text(encoding='utf-8'))['name']==name:matches.append(file.parent)
                except (ValueError,UnicodeError,OSError):continue
            if len(matches)!=1:raise ValueError('The original revision does not identify one matching skill. Choose its precise folder through Import.')
            baseline=matches[0];validate_folder(baseline)
            with manager.lock:
                if tree_digest(folder)!=expected or manager.registry.get(str(folder),{})!=record:raise ValueError('Installed skill changed during baseline review.')
                token=uuid.uuid4().hex;dest=manager.state/'baselines'/token;dest.parent.mkdir(exist_ok=True)
                shutil.copytree(baseline,dest,ignore=shutil.ignore_patterns('.git'))
                manager.registry[str(folder)]=dict(record,upstream=dict(repo=repo,commit=resolved,ref='',path=baseline.relative_to(root).as_posix()),baseline=token)
                manager.save()
        return self.provenance(folder)

    def provenance(self,folder):
        folder=Path(folder);record=self.manager.registry.get(str(folder),{})
        baseline=record.get('baseline');base=self.manager.state/'baselines'/str(baseline)
        baseline_ok=bool(baseline and base.is_dir())
        archives=[]
        for file in (self.manager.state/'archive').glob('*/record.json'):
            try:
                archived=json.loads(file.read_text())
                if Path(archived['root'])/archived['id']==folder:archives.append(dict(token=file.parent.name,at=archived['archived_at']))
            except (OSError,ValueError,KeyError):continue
        return dict(record,archives=archives,location=str(folder),localChanges=bytes_map(folder)!=bytes_map(base) if baseline_ok else None,
                    baselineAvailable=baseline_ok,updates=[r for r in self.manager.transactions.records() if r.get('destination')==str(folder)])

    def pin(self,folder,revision):
        if not isinstance(revision,str) or len(revision)>200 or revision.startswith('-') or any(c.isspace() for c in revision):raise ValueError('Invalid pin.')
        with self.manager.lock:
            record=self.manager.registry.get(str(folder))
            if not record or not record.get('upstream'):raise ValueError('This skill has no recorded upstream source.')
            if revision=='installed':revision=record['upstream']['commit']
            if revision and not re.fullmatch(r'[a-f0-9]{40}',revision):raise ValueError('Pin a full commit ID. Check a branch or tag first to resolve its immutable revision.')
            record['pin']=revision;self.manager.save()
        return self.provenance(folder)

    def check(self,folder,ref='',progress=None):
        from management import validate_folder
        manager=self.manager;folder=Path(folder)
        with manager.lock:
            record=dict(manager.registry.get(str(folder),{}));origin=record.get('upstream')
            if not origin or not record.get('baseline'):raise ValueError('This import predates upstream tracking. Import its exact installed revision once to establish a comparison baseline.')
            if len(self.previews)>=10:raise ValueError('Discard an update review before checking another.')
            expected=tree_digest(folder);local=bytes_map(folder)
            baseline=manager.state/'baselines'/record['baseline']
            base=bytes_map(baseline)
        if progress:progress('downloading','Checking upstream revision')
        with tempfile.TemporaryDirectory(prefix='skilldesk-upstream-') as work:
            repo=Path(work)/'repo';commit=checkout(origin['repo'],ref or record.get('pin') or origin.get('ref',''),repo)
            selected=repo/origin['path']
            if selected.is_symlink() or not selected.resolve().is_relative_to(repo.resolve()):raise ValueError('Upstream folder is outside the repository.')
            validate_folder(selected);remote=bytes_map(selected)
            merged,conflicts,changes,renames=merge_files(base,local,remote)
            if tree_digest(folder)!=expected:raise ValueError('Installed files changed during the check. Check again.')
            token=uuid.uuid4().hex
            snapshot=Path(manager.temporary.name)/('upstream-'+token);shutil.copytree(selected,snapshot)
            review=dict(id=token,folder=str(folder),expected=expected,commit=commit,previous=origin['commit'],ref=ref or record.get('pin') or origin.get('ref',''),
                        changes=changes,conflicts=conflicts,renames=renames,upToDate=not changes,localChanges=local!=base)
            self.previews[token]=dict(review=review,merged=merged,local=local,remote=remote,snapshot=snapshot,origin=origin)
            return review

    def prepare(self,data):
        from management import validate_folder
        row=self.previews.get(data.get('id'))
        if not row:raise ValueError('Update review expired. Check again.')
        review=row['review'];folder=Path(review['folder'])
        if tree_digest(folder)!=review['expected']:raise ValueError('Installed files changed after update review.')
        choices=data.get('resolutions',{})
        if not isinstance(choices,dict):raise ValueError('Choose how to resolve each conflicting file.')
        merged=dict(row['merged'])
        for conflict in review['conflicts']:
            name=conflict['file'];choice=choices.get(name)
            if not isinstance(choice,dict) or choice.get('side') not in {'local','upstream','custom'}:raise ValueError('Resolve conflict: '+name)
            if choice['side']=='custom':
                value=choice.get('content')
                if not isinstance(value,str) or len(value.encode())>200000:raise ValueError('Custom resolution must be text up to 200 KB.')
                content=value.encode()
            else:content=row['local' if choice['side']=='local' else 'remote'].get(name)
            if content is None:merged.pop(name,None)
            else:merged[name]=content
        with tempfile.TemporaryDirectory(prefix='skilldesk-update-') as work:
            root=Path(work)
            for name,content in merged.items():
                path=root/name;path.parent.mkdir(parents=True,exist_ok=True);path.write_bytes(content)
                # Preserve installed executable modes where the file survives.
                original=folder/name if (folder/name).is_file() else row['snapshot']/name
                if original.is_file():path.chmod(original.stat().st_mode & 0o777)
            validate_folder(root)
            result=self.manager.stage([root],'Repo Installed',row['origin']['repo']+'@'+review['commit']+':'+row['origin']['path'],folder.parent,[folder.parent])
            draft=self.manager.drafts[result['draft']]
            draft['upstream']={'0':dict(row['origin'],commit=review['commit'],ref=review['ref'])}
            draft['baselines']={'0':row['snapshot']}
            draft['updateExpected']=review['expected']
            result['updateReview']=review
            return result

    def discard(self,token):
        row=self.previews.pop(token,None)
        if row and not any(row['snapshot'] in draft.get('baselines',{}).values() for draft in self.manager.drafts.values()):shutil.rmtree(row['snapshot'],ignore_errors=True)
        return dict(discarded=bool(row))
