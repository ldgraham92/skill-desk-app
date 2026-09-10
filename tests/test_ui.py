import json
from pathlib import Path
import re
import shutil
import subprocess
import sys
import unittest

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT/'scripts'))
from skill_desk import live_html


@unittest.skipUnless(shutil.which('node'), 'Node is required for UI checks')
class UIContractTests(unittest.TestCase):
    def test_live_copy_uses_provider_and_real_name(self):
        # Exercise the actual served template, which replaces the offline overview.
        page = live_html().decode()
        helpers = page[page.index('function skillName'):page.index('function overview')]
        copy = page[page.index('async function copy'):page.index("document.addEventListener('click',async e=>")]
        program = helpers + copy + r'''
const assert=require('node:assert/strict');
let harnessFilter='all',copied='';
const skills=[{id:'library-hash-example',name:'example',harnesses:['codex','claude'],prompt:'Use $example with /example/resources and $example-other. Cost $20.'}];
const navigator={clipboard:{writeText:async text=>{copied=text}}};
function toast(){}
(async()=>{
 assert.equal(skillInvocation(skills[0]),'$example');
 harnessFilter='claude';
 assert.equal(skillInvocation(skills[0]),'/example');
 await copy(skills[0].id);
 assert.equal(copied,'Use /example with /example/resources and $example-other. Cost $20.');
 harnessFilter='codex';skills[0].prompt='/example Inspect this.';
 await copy(skills[0].id);assert.equal(copied,'$example Inspect this.');
 harnessFilter='all';skills[0].harnesses=['claude'];
 assert.equal(skillInvocation(skills[0]),'/example');
})();
'''
        subprocess.run(['node', '-e', program], check=True, timeout=15, capture_output=True)

    def test_served_and_portable_scripts_parse(self):
        pages = [live_html().decode(), (ROOT/'marketing/index.html').read_text(encoding='utf-8'), (ROOT/'desktop/updater.html').read_text(encoding='utf-8')]
        for page in pages:
            for attrs, script in re.findall(r'<script([^>]*)>(.*?)</script>', page, re.S):
                if 'application/json' in attrs or 'src=' in attrs: continue
                subprocess.run(['node', '--check'], input=script, text=True, encoding='utf-8', check=True, timeout=15, capture_output=True)
        subprocess.run([sys.executable, str(ROOT/'scripts/sync_ui_assets.py'), '--check'], check=True, timeout=15)

    def test_theme_is_injected_before_first_paint(self):
        page=live_html(saved=['example'], theme='light').decode()
        self.assertLess(page.index('window.skillDeskTheme="light"'),page.index("const key='skill-desk-theme'"))
        self.assertIn('let saved=["example"]',page)
        self.assertIn('window.skillDeskTheme="dark"',live_html(theme='<script>').decode())
