"""Publish immutable installers, then advance the public signed-update feed."""
import base64
import hashlib
import json
import os
from pathlib import Path
import subprocess

ROOT=Path(__file__).resolve().parent.parent
REPO='ldgraham92/skill-desk'
def gh(*args, data=None):
    command=['gh',*args]
    if data is not None: command+=['--input','-']
    return subprocess.check_output(command,input=json.dumps(data).encode() if data is not None else None)

def manifest(folder, tag, notes):
    platforms={}
    for path in folder.glob('updater-*.json'): platforms.update(json.loads(path.read_text()))
    required={'windows-x86_64','darwin-aarch64','linux-x86_64'}
    if set(platforms)!=required: raise RuntimeError('Missing signed updater platforms')
    for entry in platforms.values():
        if not entry['signature'] or not entry['url'].startswith(f'https://github.com/{REPO}/releases/download/{tag}/'):
            raise RuntimeError('Invalid updater artifact')
    return {'version':tag.removeprefix('v'),'notes':notes,'platforms':platforms}

def publish_feed(feed):
    # A separate branch supports preview releases without GitHub's /latest redirect.
    ref=f'repos/{REPO}/git/ref/heads/updates'
    try:
        previous=json.loads(gh('api',ref))['object']['sha']
        current=json.loads(gh('api',f'repos/{REPO}/contents/latest.json?ref=updates'))
        old=json.loads(base64.b64decode(current['content']))
        if tuple(map(int,old['version'].split('.')))>=tuple(map(int,feed['version'].split('.'))): return
    except subprocess.CalledProcessError: previous=None
    tree=json.loads(gh('api',f'repos/{REPO}/git/trees','--method','POST',data={'tree':[{'path':'latest.json','mode':'100644','type':'blob','content':json.dumps(feed,indent=2)+'\n'}]}))['sha']
    commit=json.loads(gh('api',f'repos/{REPO}/git/commits','--method','POST',data={'message':'Publish update feed '+feed['version'],'tree':tree,'parents':[previous] if previous else []}))['sha']
    if previous: gh('api',f'repos/{REPO}/git/refs/heads/updates','--method','PATCH',data={'sha':commit,'force':False})
    else: gh('api',f'repos/{REPO}/git/refs','--method','POST',data={'ref':'refs/heads/updates','sha':commit})

def main():
    os.chdir(ROOT)
    tag=os.environ['RELEASE_TAG'];folder=ROOT/'release-assets'
    notes=(ROOT/'docs/releases'/f'{tag}.md').read_text()
    feed=manifest(folder,tag,notes)
    (folder/'latest.json').write_text(json.dumps(feed,indent=2)+'\n')
    assets=sorted(p for p in folder.iterdir() if not p.name.startswith('updater-') and p.name!='SHA256SUMS.txt')
    for extension in ('.exe','.dmg','.deb','.AppImage'):
        if not any(p.suffix==extension for p in assets): raise RuntimeError(f'Missing {extension} installer')
    checksums=folder/'SHA256SUMS.txt'
    checksums.write_text(''.join(f'{hashlib.sha256(p.read_bytes()).hexdigest()}  {p.name}\n' for p in assets));assets.append(checksums)
    existing=subprocess.run(['gh','release','view',tag],capture_output=True)
    if existing.returncode==0: raise RuntimeError('Release already exists; inspect before retrying publication.')
    command=['release','create',tag,'--verify-tag','--title',f'Skill-Desk {tag}','--notes-file',str(ROOT/'docs/releases'/f'{tag}.md')]
    if tag.startswith('v0.') or '-' in tag: command.append('--prerelease')
    gh(*command,*map(str,assets))
    publish_feed(feed)
    print('Release published; update feed advanced.')
if __name__=='__main__': main()
