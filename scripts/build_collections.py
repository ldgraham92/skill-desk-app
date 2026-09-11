"""Build bundled packages from reviewed, pinned local upstream checkouts."""
import argparse
import base64
import hashlib
import json
from pathlib import Path
import re
import shutil
import subprocess
import tempfile

from skill_packages import export_package
from management import metadata

ROOT = Path(__file__).resolve().parent.parent
SOURCES = [
    dict(id='ai-hero', name='AI Hero', repo='mattpocock/skills', folder='skills', license='LICENSE', commit='3cca18b368ae95cdbdebbff572ccafa662551015', description='Engineering, debugging, planning and writing skills from Matt Pocock. Includes upstream in-progress skills.'),
    dict(id='pstack', name='PStack', repo='cursor/plugins', folder='pstack/skills', license='pstack/LICENSE', commit='c9ce35f013e234eb4de5ce15e1ca322998bb05ea', description='Engineering principles, verification, design and writing skills from Lauren Tan.'),
]


def build(source, checkout, output):
    checkout = Path(checkout).resolve()
    commit = subprocess.check_output(['git', '-C', str(checkout), 'rev-parse', 'HEAD'], text=True).strip()
    if commit != source['commit']: raise ValueError('Checkout must match the pinned commit for '+source['name'])
    if subprocess.check_output(['git', '-C', str(checkout), 'status', '--porcelain'], text=True).strip():
        raise ValueError('Use an unmodified upstream checkout.')
    folders = sorted({p.parent for p in (checkout/source['folder']).rglob('SKILL.md') if '.git' not in p.parts})
    changes, skills, entries = [], [], []
    with tempfile.TemporaryDirectory(prefix='skilldesk-collection-') as tmp:
        for i, folder in enumerate(folders):
            dest = Path(tmp)/str(i)
            shutil.copytree(folder, dest, symlinks=True)
            entry = dest/'SKILL.md'
            text = entry.read_text(encoding='utf-8')
            # Two upstream display names need portable invocation names.
            if source['id'] == 'pstack' and folder.name in {'make-bot-ui', 'poteto-mode'}:
                text = re.sub(r'(?m)^name: .*$', 'name: '+folder.name, text, count=1)
                changes.append(str(folder.relative_to(checkout))+': normalized invocation name')
            # Cross-skill references must work when only one skill is installed.
            def link(match):
                target = (folder/match[1]).resolve()
                if not target.is_relative_to(checkout) or not target.is_file():
                    raise ValueError('Unresolved upstream reference: '+match[1])
                changes.append(str(folder.relative_to(checkout))+': pinned reference '+match[1])
                return '](https://github.com/'+source['repo']+'/blob/'+commit+'/'+target.relative_to(checkout).as_posix()+')'
            text = re.sub(r'\]\((\.\./[^)]+)\)', link, text)
            entry.write_text(text, encoding='utf-8')
            (dest/'SKILLDESK-UPSTREAM-LICENSE.txt').write_bytes((checkout/source['license']).read_bytes())
            (dest/'SKILLDESK-SOURCE.txt').write_text('Source: https://github.com/'+source['repo']+'/tree/'+commit+'/'+folder.relative_to(checkout).as_posix()+'\nPackaged by Skill-Desk. See the bundled collection catalog for adaptations.\n', encoding='utf-8')
            entries.append(dict(folder=dest))
            skills.append(dict(path=folder.relative_to(checkout).as_posix(), description=metadata(text)['description']))
        package = export_package(entries)
    raw = base64.b64decode(package['data'])
    for skill, packaged in zip(skills, package['manifest']['skills']): skill['name'] = packaged['name']
    filename = source['id']+'.skilldesk.zip'
    output.mkdir(parents=True, exist_ok=True)
    (output/filename).write_bytes(raw)
    return dict(source, url='https://github.com/'+source['repo']+'/tree/'+commit+'/'+source['folder'], filename=filename, count=len(skills), bytes=len(raw), sha256=hashlib.sha256(raw).hexdigest(), skills=skills, adaptations=changes)


if __name__ == '__main__':
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('ai_hero_checkout', type=Path)
    parser.add_argument('pstack_checkout', type=Path)
    args = parser.parse_args()
    output = ROOT/'web/collections'
    catalog = [build(source, checkout, output) for source, checkout in zip(SOURCES, [args.ai_hero_checkout, args.pstack_checkout])]
    (output/'catalog.json').write_text(json.dumps(catalog, indent=2)+'\n', encoding='utf-8')
    print(', '.join(f"{c['name']}: {c['count']} skills" for c in catalog))
