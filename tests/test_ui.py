import json
from html.parser import HTMLParser
from pathlib import Path
import shutil
import subprocess
import sys
import unittest

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT/'scripts'))
from skill_desk import live_html


class ScriptParser(HTMLParser):
    """Collect scripts for syntax checks, not for HTML sanitization."""
    def __init__(self, page):
        super().__init__(convert_charrefs=False)
        self.scripts = []
        self.current = None
        self.feed(page)
        self.close()

    def handle_starttag(self, tag, attrs):
        if tag == 'script':
            self.current = (dict(attrs), [])

    def handle_data(self, data):
        if self.current is not None:
            self.current[1].append(data)

    def handle_endtag(self, tag):
        if tag == 'script' and self.current is not None:
            attrs, parts = self.current
            self.scripts.append((attrs, ''.join(parts)))
            self.current = None


@unittest.skipUnless(shutil.which('node'), 'Node is required for UI checks')
class UIContractTests(unittest.TestCase):
    def test_completed_job_without_result_shows_status_without_rendering_or_retry(self):
        source = (ROOT/'web/manage.js').read_text()
        functions = source[source.index('let jobState=null'):source.index('async function startJob')]
        program = r'''
const assert=require('node:assert/strict');
let activeJob=null,activeDraft=null,recommendationResult=null,lastToolResult=null;
let dialog='',progressVisible=false,apiCalls=0,response;
const modal={open:true};
const element={textContent:'',classList:{toggle(){}},querySelector(){return {...element}},querySelectorAll(){return []}};
const banner={...element,dataset:{},setAttribute(){},innerHTML:''};
const document={createElement:()=>banner};
const sessionStorage={setItem(){},removeItem(){}};
function $(selector){if(selector==='.topbar')return {after(){}};if(selector==='#job-progress')return progressVisible?element:null;return element;}
function esc(text){return text;}
function dialogHeader(title){return title;}
function showDialog(html){dialog=html;progressVisible=html.includes('id="job-progress"');}
function toast(){}
function specialJob(job){return job.action==='workbench';}
function showToolResult(){assert.fail('Missing result reached tool renderer');}
function showRecommendationResult(){assert.fail('Missing result reached recommendation renderer');}
function previewDraft(){assert.fail('Missing result reached draft renderer');}
function setTimeout(){assert.fail('Terminal job polled again');}
async function api(){apiCalls++;return response;}
''' + functions + r'''
(async()=>{
 for(const action of ['recommend','create','workbench']){
  response={action,status:'complete',phase:'ready',resultAvailable:false,message:'This job completed, but its result is no longer available.'};
  apiCalls=0;await waitForJob('fixture',action);
  assert.equal(apiCalls,1);assert.equal(activeJob,null);assert.equal(jobConnectionLost,false);
  assert.match(dialog,/Job completed/);assert.match(dialog,/result is no longer available/);
  assert.doesNotMatch(banner.innerHTML,/View recommendations|Review skill|ready to review|recommendations are ready/);
  assert.match(banner.innerHTML,/View status/);assert.match(banner.innerHTML,/dismiss-skill-job/);
  showJobProgress();assert.match(dialog,/result is no longer available/);
 }
})().catch(error=>{console.error(error);process.exitCode=1;});
'''
        result = subprocess.run(['node', '-e', program], timeout=15, capture_output=True, text=True)
        self.assertEqual(result.returncode, 0, result.stderr)

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
 harnessFilter='cursor';assert.equal(skillInvocation(skills[0]),'/example');
 harnessFilter='opencode';await copy(skills[0].id);assert.equal(copied,'Use example skill with /example/resources and $example-other. Cost $20.');
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
            for attrs, script in ScriptParser(page).scripts:
                if attrs.get('type') == 'application/json' or 'src' in attrs: continue
                subprocess.run(['node', '--check'], input=script, text=True, encoding='utf-8', check=True, timeout=15, capture_output=True)
        for external in ['manage.js', 'workspace.js', 'onboarding.js', 'experience.js']:
            subprocess.run(['node', '--check', str(ROOT/'web'/external)], check=True, timeout=15, capture_output=True)
        subprocess.run([sys.executable, str(ROOT/'scripts/sync_ui_assets.py'), '--check'], check=True, timeout=15)

    def test_walkthrough_images_are_bundled_at_high_resolution(self):
        import struct
        for name in ['library','projects','discover','recommendations','first-step']:
            content=(ROOT/'web/walkthrough'/f'{name}.png').read_bytes()
            self.assertEqual(content[:8],b'\x89PNG\r\n\x1a\n')
            width,height=struct.unpack('>II',content[16:24])
            self.assertGreaterEqual(width,1500)
            self.assertGreaterEqual(height,600)
        self.assertIn('/onboarding.js',live_html().decode())

    def test_theme_is_injected_before_first_paint(self):
        page=live_html(saved=['example'], theme='light').decode()
        self.assertLess(page.index('window.skillDeskTheme="light"'),page.index("const key='skill-desk-theme'"))
        self.assertIn('let saved=["example"]',page)
        self.assertIn('window.skillDeskTheme="dark"',live_html(theme='<script>').decode())


class PublicContentTests(unittest.TestCase):
    def test_script_parser_handles_case_attributes_and_end_tag_whitespace(self):
        page = '<SCRIPT data-note="a > b">const upper = 1;</SCRIPT ><script src = "app.js"></script><script type="application/json">{"ok":true}</script>'
        self.assertEqual(ScriptParser(page).scripts, [
            ({'data-note': 'a > b'}, 'const upper = 1;'),
            ({'src': 'app.js'}, ''),
            ({'type': 'application/json'}, '{"ok":true}'),
        ])

    def test_public_root_is_marketing_and_desktop_has_no_seed_catalog(self):
        marketing = (ROOT/'marketing/index.html').read_text(encoding='utf-8')
        self.assertEqual((ROOT/'index.html').read_text(encoding='utf-8'), marketing)
        self.assertNotIn('/api/skills', marketing)
        template = (ROOT/'web/app.html').read_text(encoding='utf-8')
        catalog = next(script for attrs, script in ScriptParser(template).scripts if attrs.get('id') == 'skill-data')
        self.assertEqual(json.loads(catalog), [])
        self.assertIn('/api/skills', live_html().decode())
