"""Read-only comparisons and library health checks."""
import difflib
from pathlib import Path
from management import validate_folder, inventory
from job_control import checkpoint
from advanced_drafts import file_diff


def compare(left,right):
    left,right=Path(left),Path(right)
    a,b=inventory(left),inventory(right)
    changed=sorted(name for name in set(a)&set(b) if (left/name).read_bytes()!=(right/name).read_bytes())
    diff='\n'.join(difflib.unified_diff((left/'SKILL.md').read_text(encoding='utf-8').splitlines(),(right/'SKILL.md').read_text(encoding='utf-8').splitlines(),fromfile='First copy',tofile='Second copy',lineterm=''))
    return dict(fileChanges=[file_diff((left/name).read_bytes() if name in a else None,(right/name).read_bytes() if name in b else None,name) for name in sorted(set(changed)|set(a)^set(b))],identical=not changed and set(a)==set(b),changed=changed,added=sorted(set(b)-set(a)),removed=sorted(set(a)-set(b)),
                diff=diff[:100000],truncated=len(diff)>100000,left=str(left),right=str(right))


def health(entries,projects):
    issues=[];checked=0
    for item in entries[:2000]:
        checkpoint()
        folder=Path(item['folder']);checked+=1
        try:
            from library_tools import quality
            report=quality(folder,item.get('harnesses',[]))
            issues.extend(dict(name=item['name'],location=str(folder),**issue) for issue in report['issues'])
        except Exception as error:
            issues.append(dict(name=item['name'],location=str(folder),message=str(error)))
    for project in projects:
        if not project.get('available'): issues.append(dict(name=project['name'],location=project['path'],message='Registered project is unavailable.'))
    return dict(checked=checked,issues=issues,partial=len(entries)>checked)
