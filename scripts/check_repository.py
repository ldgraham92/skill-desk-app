"""Check the public app workspace boundary before packaging or publication."""
from pathlib import Path
import ast

ROOT = Path(__file__).resolve().parents[1]
for name in ('marketing', 'index.html', 'docs/MARKETING.md'):
    if (ROOT / name).exists():
        raise SystemExit('Website content does not belong in the app repository: ' + name)
for path in (ROOT / 'src/skilldesk').glob('*.py'):
    tree = ast.parse(path.read_text(encoding='utf-8'))
    modules = {p.stem for p in (ROOT / 'src/skilldesk').glob('*.py')}
    for node in ast.walk(tree):
        if isinstance(node, ast.ImportFrom) and node.level == 0 and node.module in modules:
            raise SystemExit('Use a package-relative import: ' + str(path))
        if isinstance(node, ast.Import) and any(n.name in modules for n in node.names):
            raise SystemExit('Use a package-relative import: ' + str(path))
print('App repository boundary and package imports passed.')
