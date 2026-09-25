"""Application actions for reviewed library maintenance."""
import hashlib
import json
import os
from pathlib import Path
import shutil
import time
import uuid
from durable_state import StateFile,atomic_json,digest
from experience import tree_digest
from library_tools import LibraryTools,quality
from workspace_backup import WorkspaceBackup


class Workbench:
    def __init__(self,manager,catalog,projects,recommendations):
        self.manager,self.catalog,self.projects,self.recommendations=manager,catalog,projects,recommendations
        self.library=LibraryTools(manager.state)
        self.backup=WorkspaceBackup(manager)
        self.history=StateFile(manager.state/'history-options.json',{})
        self.history.value.setdefault('projects',[]);self.history.value.setdefault('locations',[])
        self.moves={};self.samples={}

    def entries(self):
        favorites=StateFile(self.manager.state/'preferences.json',{}).value.get('saved',[])
        with self.catalog.lock:
            return [dict(row,favorite=row['id'] in favorites,folder=str(Path(self.catalog.files[row['id']]).parent),project=self.projects.scope(row['library'])) for row in self.catalog.snapshot()['skills']]

    def entry(self,key):
        item=next((r for r in self.entries() if r['id']==key),None)
        if not item:raise ValueError('Skill is no longer in the library. Refresh and choose again.')
        return item

    def favorite(self,ids,value):
        store=StateFile(self.manager.state/'preferences.json',{})
        saved=set(store.value.get('saved',[]))
        if value:saved.update(ids)
        else:saved.difference_update(ids)
        store.save(dict(store.value,saved=sorted(saved)))

    def recommendation_choices(self):
        rows=[];entries=self.entries()
        for choice in self.manager.experience.data['choices']:
            project=next((p for p in self.projects.listing() if p['id']==choice['project']),None)
            available={e['name']:dict(name=e['name'],description=e.get('summary','')[:1200]) for e in entries if choice['agent'] in e.get('harnesses',[]) and (not e.get('project') or e['project']==choice['project'])}
            current=self.recommendations.context_digest(list(available.values()),project,choice['agent'])
            freshness='Freshness unknown for this older saved suggestion.' if not choice.get('contextDigest') else 'Inputs changed since this suggestion was saved.' if current!=choice['contextDigest'] else 'Installed skill descriptions and project notes still match the reviewed inputs.'
            rows.append(dict(choice,freshness=freshness,satisfied=choice['name'] in available))
        return rows

    def handle(self,data):
        manager=self.manager;op=data.get('op')
        if op=='overview':
            return dict(entries=self.entries(),organization=self.library.data,recovery=manager.transactions.records(),interrupted=manager.interrupted_jobs,
                        warnings=[store.error for store in (manager.registry_store,manager.job_records,manager.experience.store,self.projects.store,self.library.store,self.history) if store.error],exclusions=self.history.value)
        if op=='search':return self.library.search(self.entries(),data.get('query',{}),manager.registry)
        if op=='search-save':return self.library.saved_search(data)
        if op=='annotate':
            result=self.library.annotate(self.entry(data.get('id'))['folder'],data)
            if 'favorite' in data:self.favorite([data['id']],data['favorite'])
            return result
        if op=='duplicates':return self.library.duplicates(self.entries())
        if op=='collections':return self.library.collection_coverage(self.entries())
        if op=='quality':
            entry=self.entry(data.get('id'));return quality(entry['folder'],data.get('agents') or entry['harnesses'])
        if op=='provenance':return manager.upstream.provenance(Path(self.entry(data.get('id'))['folder']))
        if op=='pin':return manager.upstream.pin(Path(self.entry(data.get('id'))['folder']),data.get('revision',''))
        if op=='upstream-baseline':
            entry=self.entry(data.get('id'));folder=Path(entry['folder'])
            def establish(payload,progress):
                manager.upstream.bootstrap(folder,progress)
                return dict(workbenchResult={'id':entry['id']},workbenchType='provenance')
            return manager.job('workbench',data,establish)
        if op=='update-check':
            folder=Path(self.entry(data.get('id'))['folder'])
            return manager.job('workbench',data,lambda payload,progress:dict(workbenchResult=manager.upstream.check(folder,payload.get('revision',''),progress),workbenchType='update'))
        if op=='updates-check':
            ids=data.get('ids')
            if not isinstance(ids,list) or not 1<=len(ids)<=10:raise ValueError('Check between 1 and 10 upstream sources at a time.')
            folders=[Path(self.entry(key)['folder']) for key in ids]
            def check_many(payload,progress):
                results=[]
                for folder in folders:
                    try:results.append(dict(folder=str(folder),review=manager.upstream.check(folder,'',progress)))
                    except Exception as error:results.append(dict(folder=str(folder),error=str(error)))
                return dict(workbenchResult=results,workbenchType='updates')
            return manager.job('workbench',data,check_many)
        if op=='update-prepare':return manager.upstream.prepare(data)
        if op=='update-discard':return manager.upstream.discard(data.get('id'))
        if op=='rollback-preview':
            entry=self.entry(data.get('id'));folder=Path(entry['folder']);token=data.get('token')
            if not isinstance(token,str) or len(token)!=32 or any(c not in '0123456789abcdef' for c in token):raise ValueError('Invalid archive record.')
            base=manager.state/'archive'/token;record=json.loads((base/'record.json').read_text())
            if Path(record['root'])/record['id']!=folder:raise ValueError('Archive belongs to another destination.')
            result=manager.stage([base/'skill'],record['origin'].get('kind','Existing'),'Rollback of '+record.get('archived_at',''),folder.parent,[folder.parent])
            origin=record['origin']
            if origin.get('upstream') and origin.get('baseline'):
                draft=manager.drafts[result['draft']]
                draft['upstream']={'0':origin['upstream']}
                draft['baselines']={'0':manager.state/'baselines'/origin['baseline']}
            return result
        if op=='recovery-preview':return manager.transactions.preview(data.get('id'))
        if op=='recovery-apply':
            record=manager.transactions.recover(data.get('id'),data.get('expected'),data.get('mode'))
            if record.get('fileMode'):
                manager.restoreRestartRequired=True
                return dict(record,restartRequired=True)
            manager.registry[record['destination']]=record.get('origin',{}) if data.get('mode')=='before' else dict(kind='Existing',source='Recovered local operation')
            manager.save();self.catalog.refresh(generate=False);return record
        if op=='draft-files':return manager.file_changes(data)
        if op=='draft-replace-text':return manager.replace_text(data)
        if op=='draft-revisions':return manager.folder_revisions(data)
        if op=='draft-restore':return manager.restore_revision(data)
        if op=='draft-export':return manager.export_draft(data)
        if op=='draft-template':return manager.save_draft(dict(data,template=True))
        if op=='draft-fork':
            from agents import personal_root,LABELS
            target=data.get('target')
            if target not in LABELS:raise ValueError('Choose a destination agent.')
            draft,folder=manager.draft_candidate(data)
            return manager.fork_folder(draft,folder,personal_root(target),target)
        if op=='batch':
            ids=data.get('ids');action=data.get('action')
            if not isinstance(ids,list) or not 1<=len(ids)<=500 or len(set(ids))!=len(ids):raise ValueError('Select 1 to 500 distinct skills.')
            entries=[self.entry(key) for key in ids]
            if action=='export':
                from skill_packages import export_package
                accepted=[];results=[]
                for entry in entries:
                    try:
                        export_package([entry])
                        accepted.append(entry);results.append(dict(id=entry['id'],status='exported'))
                    except Exception as error:results.append(dict(id=entry['id'],status='failed',message=str(error)))
                if not accepted:return dict(results=results)
                return dict(export_package(accepted),results=results)
            results=[]
            for entry in entries:
                try:
                    if action=='favorite':
                        self.library.annotate(entry['folder'],dict(favorite=data.get('favorite',True)))
                        self.favorite([entry['id']],data.get('favorite',True))
                    elif action=='archive':
                        from management import fingerprint
                        folder=Path(entry['folder'])
                        if folder.parent!=manager.root:raise ValueError('Batch archive is available only in the managed library.')
                        expected=data.get('fingerprints',{}).get(entry['id'])
                        if expected!=fingerprint(folder):raise ValueError('Archive selection changed. Review it again.')
                        manager.archive(dict(id=folder.name,fingerprint=expected))
                    else:raise ValueError('Unknown batch action.')
                    results.append(dict(id=entry['id'],status='done'))
                except Exception as error:results.append(dict(id=entry['id'],status='failed',message=str(error)))
            self.catalog.refresh(generate=False);return dict(results=results)
        if op=='batch-review':
            from management import fingerprint
            return dict(items=[dict(self.entry(key),fingerprint=fingerprint(Path(self.entry(key)['folder']))) for key in data.get('ids',[])[:500]])
        if op=='collection-quality':
            entries=[e for e in self.entries() if data.get('name') in self.library.data['skills'].get(e['folder'],{}).get('collections',[])]
            return dict(collection=data.get('name'),reports=[dict(name=e['name'],location=e['folder'],**quality(e['folder'],e['harnesses'])) for e in entries])
        if op=='collection-preview':
            from agents import personal_root,LABELS
            target=data.get('target')
            if target not in LABELS:raise ValueError('Choose a supported agent.')
            entries=[e for e in self.entries() if data.get('name') in self.library.data['skills'].get(e['folder'],{}).get('collections',[])]
            if not entries:raise ValueError('Collection is empty.')
            root=personal_root(target)
            result=manager.stage([Path(e['folder']) for e in entries],'Harness Copy','Local collection '+data['name'],root,[root])
            for candidate,entry in zip(result['candidates'],entries):candidate['compatibility']=quality(entry['folder'],[target])
            manager.drafts[result['draft']]['target_agent']=target
            result['package']=True
            seen=set()
            for candidate in result['candidates']:
                if candidate['name'] in seen:candidate['conflict']='Another copy with this name is already included. Review copies separately.'
                seen.add(candidate['name'])
            return result
        if op=='backup-export':return self.backup.export([self.entry(key) for key in data.get('ids',[])],data.get('settings') is True,data.get('drafts') is True)
        if op=='backup-preview':return self.backup.preview(data,set(self.catalog.roots))
        if op=='backup-restore':
            result=self.backup.restore(data)
            if result['restartRequired']:manager.restoreRestartRequired=True
            self.catalog.refresh(generate=False);return result
        if op=='backup-discard':
            row=self.backup.previews.pop(data.get('id'),None)
            if row:shutil.rmtree(row['base'])
            return dict(discarded=bool(row))
        if op=='project-reconnect-preview':
            from projects import project_destination
            from agents import LABELS
            project=self.projects.get(data.get('id'));path=Path(str(data.get('path',''))).expanduser().resolve()
            for agent in LABELS:project_destination(path,agent)
            if any(p['path']==str(path) and p['id']!=project['id'] for p in self.projects.listing()):raise ValueError('This repository is already registered.')
            token=uuid.uuid4().hex;self.moves[token]=dict(kind='project',project=project,path=str(path))
            return dict(id=token,old=project['path'],new=str(path),name=project['name'])
        if op=='project-reconnect':
            from projects import project_destination
            from agents import LABELS
            row=self.moves.get(data.get('id'))
            if not row or row['kind']!='project':raise ValueError('Reconnect preview expired.')
            for agent in LABELS:project_destination(row['path'],agent)
            project=self.projects.get(row['project']['id'])
            if project!=row['project']:raise ValueError('Project registration changed. Review it again.')
            for item in self.projects.items:
                if item['id']==project['id']:item['path']=row['path']
            self.projects.save()
            old=Path(project['path']);new=Path(row['path'])
            for key in list(manager.registry):
                if Path(key).resolve().is_relative_to(old.resolve()):manager.registry[str(new/Path(key).resolve().relative_to(old.resolve()))]=manager.registry.pop(key)
            manager.save()
            for key in list(self.library.data['skills']):
                if Path(key).resolve().is_relative_to(old.resolve()):self.library.data['skills'][str(new/Path(key).resolve().relative_to(old.resolve()))]=self.library.data['skills'].pop(key)
            self.library.store.save(self.library.data)
            self.catalog.roots=[p for p in self.catalog.roots if not p.resolve().is_relative_to(old.resolve())]+self.projects.roots();self.catalog.refresh(generate=False)
            return dict(reconnected=True)
        if op=='relocate-preview':
            if os.name=='nt':raise ValueError('Library relocation needs a verified Windows directory-link workflow. Keep the current location on Windows.')
            source=manager.root
            if self.projects.scope(source):raise ValueError('Project skill directories must stay inside their repository. Relocate only a personal managed library.')
            target=Path(str(data.get('path',''))).expanduser().resolve()
            if source.is_symlink() or not source.is_dir():raise ValueError('Only an ordinary managed library can be relocated.')
            if not str(data.get('path','')).strip() or target.exists() or target.is_relative_to(source.resolve()) or source.resolve().is_relative_to(target):raise ValueError('Choose a new, separate directory that does not already exist.')
            token=uuid.uuid4().hex;row=dict(id=token,kind='library',source=str(source),target=str(target),expected=tree_digest(source),parent=str(target.parent.resolve()))
            self.moves[token]=row;return dict(row,message='Copy the library, preserve the original in a recovery folder, and create a directory link at its original location so agents keep finding it.')
        if op=='relocate':
            row=self.moves.get(data.get('id'))
            if not row or row['kind']!='library':raise ValueError('Relocation preview expired.')
            source,target=Path(row['source']),Path(row['target'])
            if source.is_symlink() or tree_digest(source)!=row['expected'] or target.exists() or str(target.parent.resolve())!=row['parent']:raise ValueError('Library or destination changed. Review relocation again.')
            operation=manager.transactions.begin('relocate-copy',target,source)
            target.parent.mkdir(parents=True,exist_ok=True);shutil.copytree(source,target)
            if tree_digest(target)!=row['expected'] or tree_digest(source)!=row['expected']:raise ValueError('Library changed during relocation. Original remains in place.')
            manager.relocations.save(dict(manager.relocations.value,**{str(source):str(target.resolve())}))
            saved=manager.state/'relocated-libraries'/uuid.uuid4().hex;saved.parent.mkdir(exist_ok=True)
            link=source.parent/('.skilldesk-link-'+uuid.uuid4().hex)
            try:
                link.symlink_to(target,target_is_directory=True)
                shutil.move(str(source),str(saved));link.rename(source)
            except BaseException:
                if saved.exists() and not source.exists():shutil.move(str(saved),str(source))
                if link.is_symlink():link.unlink()
                raise
            manager.transactions.phase(operation,'complete');self.catalog.refresh(generate=False)
            return dict(relocated=True,backup=str(saved),destination=str(target),linkedFrom=str(source))
        if op=='history-options':
            options={}
            for key in ('projects','locations'):
                values=data.get(key,[])
                if not isinstance(values,list) or len(values)>100 or any(not isinstance(v,str) or not v.strip() or len(v)>2000 or not Path(v).expanduser().is_absolute() for v in values):raise ValueError('Enter up to 100 absolute paths per exclusion list.')
                options[key]=values
            self.history.save(options);return options
        if op=='recommendation-runs':return dict(runs=[{k:r[k] for k in ('id','target','checkedAt','sampled','summary')} for r in self.recommendations.runs])
        if op=='recommendation-compare':return self.recommendations.compare_runs(data.get('left'),data.get('right'))
        if op=='sample-save':
            sample=self.recommendations.prepare(data,[])
            token=uuid.uuid4().hex;base=manager.state/'reviewed-samples';base.mkdir(exist_ok=True)
            if len(list(base.glob('*.json')))>=20:raise ValueError('Delete a saved sample before adding another.')
            atomic_json(base/(token+'.json'),dict(sample,savedAt=time.time()))
            return dict(saved=token)
        if op=='samples':
            rows=[]
            for file in (manager.state/'reviewed-samples').glob('*.json'):
                try:
                    value=json.loads(file.read_text());rows.append(dict(id=file.stem,target=value['target'],savedAt=value['savedAt'],count=len(value['excerpts'])))
                except (ValueError,OSError,KeyError):continue
            return dict(samples=rows)
        if op in {'sample-open','sample-delete'}:
            token=data.get('id')
            if not isinstance(token,str) or len(token)!=32 or any(c not in '0123456789abcdef' for c in token):raise ValueError('Invalid sample.')
            path=manager.state/'reviewed-samples'/(token+'.json')
            if op=='sample-delete':path.unlink();return dict(deleted=True)
            value=json.loads(path.read_text());sample=dict(value,checkedAt=value['savedAt'],sampled=len(value['excerpts']),found=len(value['excerpts']),notes=['Explicitly saved sample; refresh live history for current coverage.'],coverage={},sources=[value['target']],partial=True,limits={},breakdown=[])
            preview=uuid.uuid4().hex;self.recommendations.previews[preview]=dict(sample=sample,expires=time.time()+900)
            return dict(sample,preview=preview)
        raise ValueError('Unknown workbench action.')
