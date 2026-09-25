"""Reviewed, integrity-checked backups of explicitly selected local workspace data."""
import base64
import hashlib
import io
import json
from pathlib import Path
import shutil
import stat
import tempfile
import time
import uuid
import zipfile
from durable_state import atomic_json,atomic_bytes,digest
from experience import tree_digest
from job_control import checkpoint
from skill_packages import portable_path

SETTINGS={'preferences.json':dict,'projects.json':list,'experience.json':dict,'organization.json':dict,'provider.json':dict}
MAX_BYTES=100_000_000


class WorkspaceBackup:
    def __init__(self,manager):self.manager=manager;self.previews={}

    def export(self,entries,include_settings=False,include_drafts=False):
        from management import inventory
        objects=[];manager=self.manager
        for entry in entries:
            objects.append(dict(kind='skill',name=entry['name'],destination=str(entry['folder']),folder=Path(entry['folder']),origin=dict(manager.registry.get(str(entry['folder']),{}))))
        if include_settings:
            for name in SETTINGS:
                if (manager.state/name).is_file():objects.append(dict(kind='setting',name=name,path=manager.state/name))
        if include_drafts:
            for draft in manager.saved_drafts():objects.append(dict(kind='draft',name=draft['id'],folder=manager.state/'saved-drafts'/draft['id']))
        if not objects:raise ValueError('Select skills, settings, or saved drafts to back up.')
        manifest=dict(format='skilldesk-workspace',version=1,created=time.time(),objects=[])
        output=io.BytesIO();total=0;count=0
        with zipfile.ZipFile(output,'w',zipfile.ZIP_DEFLATED) as archive:
            for index,obj in enumerate(objects):
                checkpoint();record={k:v for k,v in obj.items() if k not in {'folder','path'}};record['files']={}
                paths={name:obj['folder']/name for name in inventory(obj['folder'])} if 'folder' in obj else {obj['name']:obj['path']}
                if obj['kind']=='skill':
                    paths={'skill/'+name:path for name,path in paths.items()}
                    baseline=obj.get('origin',{}).get('baseline')
                    if baseline:
                        base=manager.state/'baselines'/baseline
                        if base.is_dir():paths.update({'baseline/'+name:base/name for name in inventory(base)})
                before=tree_digest(obj['folder']) if 'folder' in obj else digest(obj['path'])
                for name,path in paths.items():
                    portable_path(name);content=path.read_bytes();total+=len(content);count+=1
                    if total>MAX_BYTES or count>10000:raise ValueError('Backup exceeds 100 MB or 10,000 files. Select a smaller set.')
                    record['files'][name]=hashlib.sha256(content).hexdigest()
                    info=zipfile.ZipInfo(str(index)+'/'+name);info.compress_type=zipfile.ZIP_DEFLATED;info.external_attr=(stat.S_IFREG|(path.stat().st_mode&0o777))<<16
                    archive.writestr(info,content)
                if before!=(tree_digest(obj['folder']) if 'folder' in obj else digest(obj['path'])):raise ValueError('Files changed during backup. Retry after editing has stopped.')
                manifest['objects'].append(record)
            encoded=json.dumps(manifest).encode()
            if len(encoded)>2_000_000:raise ValueError('Backup manifest is too large.')
            archive.writestr('manifest.json',encoded)
        raw=output.getvalue()
        return dict(filename='workspace.skilldesk-backup.zip',data=base64.b64encode(raw).decode(),bytes=len(raw),manifest=manifest)

    def preview(self,data,allowed_roots):
        from management import validate_folder
        if len(self.previews)>=3:raise ValueError('Discard an earlier restore review first.')
        try:raw=base64.b64decode(data.get('data',''),validate=True)
        except (ValueError,TypeError):raise ValueError('Invalid backup encoding.')
        if not 1<=len(raw)<=MAX_BYTES:raise ValueError('Choose a backup up to 100 MB.')
        token=uuid.uuid4().hex;base=Path(self.manager.temporary.name)/('restore-'+token);base.mkdir()
        try:
            with zipfile.ZipFile(io.BytesIO(raw)) as archive:
                infos=archive.infolist();seen=set()
                if len(infos)>10001 or sum(i.file_size for i in infos)>MAX_BYTES+2_000_000:raise ValueError('Expanded backup exceeds limits.')
                for info in infos:
                    portable_path(info.filename);key=info.filename.casefold()
                    if key in seen or info.is_dir() or info.flag_bits&1 or stat.S_IFMT(info.external_attr>>16) not in {0,stat.S_IFREG}:raise ValueError('Backup contains duplicate, linked, or unsupported files.')
                    seen.add(key)
                if archive.getinfo('manifest.json').file_size>2_000_000:raise ValueError('Backup manifest is too large.')
                manifest=json.loads(archive.read('manifest.json'))
                if manifest.get('format')!='skilldesk-workspace' or manifest.get('version')!=1:raise ValueError('Unsupported workspace backup.')
                objects=manifest.get('objects')
                if not isinstance(objects,list) or not 1<=len(objects)<=1000:raise ValueError('Invalid backup objects.')
                expected={'manifest.json'};reviews=[];destinations=set()
                for i,obj in enumerate(objects):
                    kind,name=obj.get('kind'),obj.get('name')
                    if kind=='setting' and name in SETTINGS:dest=self.manager.state/name
                    elif kind=='draft' and isinstance(name,str) and len(name)==32 and all(c in '0123456789abcdef' for c in name):dest=self.manager.state/'saved-drafts'/name
                    elif kind=='skill':
                        dest=Path(obj.get('destination',''))
                        if dest.parent not in allowed_roots or dest.name in {'','.','..'} or dest.is_symlink():raise ValueError('Backup destination is no longer registered: '+str(dest))
                    else:raise ValueError('Unknown backup object.')
                    if str(dest) in destinations:raise ValueError('Backup repeats a destination.')
                    destinations.add(str(dest));folder=base/str(i);folder.mkdir()
                    files=obj.get('files')
                    if not isinstance(files,dict) or not files:raise ValueError('Invalid file manifest.')
                    for rel,checksum in files.items():
                        portable_path(rel);member=str(i)+'/'+rel;expected.add(member);content=archive.read(member)
                        if hashlib.sha256(content).hexdigest()!=checksum:raise ValueError('Backup checksum mismatch.')
                        path=folder/rel;path.parent.mkdir(parents=True,exist_ok=True);path.write_bytes(content);path.chmod(0o755 if (archive.getinfo(member).external_attr>>16)&0o111 else 0o644)
                    if kind=='setting':
                        if set(files)!={name} or not isinstance(json.loads((folder/name).read_text()),SETTINGS[name]):raise ValueError('Invalid settings record.')
                    elif kind=='skill':
                        validate_folder(folder/'skill')
                        if (folder/'baseline').exists():validate_folder(folder/'baseline')
                    else:
                        validate_folder(folder/'skill')
                        record=json.loads((folder/'record.json').read_text())
                        if not isinstance(record,dict):raise ValueError('Invalid saved draft record.')
                    before=(digest(dest) if kind=='setting' else tree_digest(dest)) if dest.exists() else None
                    reviews.append(dict(index=i,kind=kind,name=name,destination=str(dest),resolvedParent=str(dest.parent.resolve()),conflict=dest.exists(),expected=before,sourceDigest=tree_digest(folder),origin=obj.get('origin',{}) if kind=='skill' else {}))
                if expected!={x.filename for x in infos}:raise ValueError('Backup includes unlisted files.')
            self.previews[token]=dict(base=base,objects=reviews)
            return dict(id=token,objects=reviews,message='Select each item to restore. Existing destinations require an explicit replacement choice. Settings take effect after restarting Skill-Desk.')
        except BaseException:shutil.rmtree(base,ignore_errors=True);raise

    def restore(self,data):
        row=self.previews.get(data.get('id'))
        if not row:raise ValueError('Restore review expired.')
        selections=data.get('selections')
        if not isinstance(selections,list) or not selections:raise ValueError('Select items to restore.')
        results=[];seen=set()
        for choice in selections:
            index=choice.get('index')
            if not isinstance(index,int) or index in seen or not 0<=index<len(row['objects']):raise ValueError('Invalid restore selection.')
            seen.add(index);obj=row['objects'][index];dest=Path(obj['destination']);kind=obj['kind'];source=row['base']/str(index)
            try:
                if obj.get('done'):results.append(dict(index=index,status='already restored'));continue
                if tree_digest(source)!=obj['sourceDigest']:raise ValueError('Prepared backup contents changed after verification. Preview the backup again.')
                if dest.is_symlink() or str(dest.parent.resolve())!=obj['resolvedParent']:raise ValueError('Destination location changed.')
                current=(digest(dest) if kind=='setting' else tree_digest(dest)) if dest.exists() else None
                if current!=obj['expected']:raise ValueError('Destination changed after preview.')
                if current is not None and choice.get('replace') is not True:raise ValueError('Review and choose replacement for this existing destination.')
                if kind=='setting':
                    operation=self.manager.transactions.begin_file('restore-settings',dest,source/dest.name)
                    atomic_bytes(dest,(source/dest.name).read_bytes())
                    self.manager.transactions.phase(operation,'complete')
                else:
                    content=source/'skill' if kind=='skill' else source
                    operation=self.manager.transactions.begin('workspace-restore',dest,content,self.manager.registry.get(str(dest),{}))
                    if dest.exists():
                        displaced=self.manager.state/'transactions'/operation['id']/'displaced'
                        shutil.move(str(dest),str(displaced))
                    dest.parent.mkdir(parents=True,exist_ok=True)
                    shutil.copytree(content,dest)
                    if tree_digest(dest)!=operation['after']:raise ValueError('Restored files failed verification. Use operation recovery.')
                    if kind=='skill':
                        origin=dict(obj['origin']) if isinstance(obj['origin'],dict) else {}
                        origin.pop('installation_id',None)
                        if (source/'baseline').is_dir():
                            baseline_id=uuid.uuid4().hex
                            baseline=self.manager.state/'baselines'/baseline_id;baseline.parent.mkdir(exist_ok=True)
                            shutil.copytree(source/'baseline',baseline);origin['baseline']=baseline_id
                        else:origin.pop('baseline',None)
                        self.manager.registry[str(dest)]=origin
                        self.manager.save()
                    self.manager.transactions.phase(operation,'complete')
                obj['done']=True;results.append(dict(index=index,status='restored'))
            except Exception as error:results.append(dict(index=index,status='failed',message=str(error)))
        return dict(results=results,restartRequired=any(r['status']=='restored' and row['objects'][r['index']]['kind']=='setting' for r in results))
