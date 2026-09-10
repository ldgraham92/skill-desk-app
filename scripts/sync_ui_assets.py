"""Embed shared theme assets so the demo and desktop windows work offline."""
from pathlib import Path
import re
import sys

ROOT = Path(__file__).resolve().parent.parent
START, END = '<!-- shared-theme:start -->', '<!-- shared-theme:end -->'
block = START + '\n<style>\n' + (ROOT/'web/theme.css').read_text(encoding='utf-8') + '</style>\n<script>\n' + (ROOT/'web/theme.js').read_text(encoding='utf-8') + '</script>\n' + END
stale = []
for name in ('index.html', 'marketing/index.html', 'desktop/index.html', 'desktop/updater.html'):
    path = ROOT/name
    source = path.read_text(encoding='utf-8')
    updated = re.sub(re.escape(START)+'.*?'+re.escape(END), lambda _: block, source, flags=re.S) if START in source else source.replace('</head>', block+'\n</head>')
    if source != updated:
        stale.append(name)
        if '--check' not in sys.argv: path.write_text(updated, encoding='utf-8')
if stale and '--check' in sys.argv:
    raise SystemExit('Run python scripts/sync_ui_assets.py to refresh: '+', '.join(stale))
