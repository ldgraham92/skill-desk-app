import json
from pathlib import Path
import sys
import tempfile
import unittest
from unittest.mock import patch
from types import SimpleNamespace
sys.path.insert(0,str(Path(__file__).resolve().parents[1]/'scripts'))
from providers import AuthorProvider
from management import Manager

class ProviderTests(unittest.TestCase):
 def setUp(self):
  patcher=patch('providers.opencode_support.capabilities',return_value={'standalone':True,'compatible':True});patcher.start();self.addCleanup(patcher.stop)
 def test_opencode_and_cursor_authoring_use_stdin_and_parse_json(self):
  for name in ('opencode','cursor'):
   with self.subTest(name=name), tempfile.TemporaryDirectory() as tmp:
    provider=AuthorProvider(Path(tmp)/'settings.json');provider.name=name;provider.models[name]='deepseek/deepseek-chat' if name=='opencode' else 'chosen-model'
    def complete(cmd,**kwargs):
     self.assertNotIn('PRIVATE BRIEF',repr(cmd));self.assertIn('PRIVATE BRIEF',kwargs['input'])
     self.assertIn('--model',cmd);self.assertEqual(cmd[cmd.index('--model')+1],provider.models[name])
     self.assertEqual(Path(kwargs['cwd']).name[:18],'skill-desk-author-')
     if name=='opencode':
      self.assertEqual(json.loads(kwargs['env']['OPENCODE_CONFIG_CONTENT'])['permission'],{'*':'deny'})
      return SimpleNamespace(returncode=0,stdout=json.dumps({'type':'text','part':{'text':'{"skill_md":"example"}'}}),stderr='')
     config=json.loads((Path(kwargs['cwd'])/'.cursor/cli.json').read_text())
     self.assertIn('Shell(*)',config['permissions']['deny']);self.assertNotIn('--force',cmd)
     return SimpleNamespace(returncode=0,stdout=json.dumps({'subtype':'success','result':'{"skill_md":"example"}'}),stderr='')
    with patch('providers.executable',return_value='/fixture/'+name),patch('providers.subprocess.run',side_effect=complete):
     self.assertEqual(provider('PRIVATE BRIEF',{'type':'object'}),{'skill_md':'example'})
    with patch('providers.subprocess.run') as run:
     with self.assertRaisesRegex(ValueError,'Isolated'):provider.generate('history',{},provider=name,analysis=True)
     run.assert_not_called()
 def test_new_cli_errors_and_model_settings(self):
  with tempfile.TemporaryDirectory() as tmp:
   settings=Path(tmp)/'settings.json';provider=AuthorProvider(settings)
   with patch('providers.executable',return_value='/fixture/opencode'):
    provider.select('opencode','deepseek/deepseek-chat')
    self.assertEqual(AuthorProvider(settings).models['opencode'],'deepseek/deepseek-chat')
    with self.assertRaises(ValueError):provider.select('opencode','--bad model')
    for output in ['not JSON',json.dumps({'type':'error','error':'PRIVATE'}),json.dumps({'type':'text','part':{'text':'{"truncated":'}})]:
     with patch('providers.subprocess.run',return_value=SimpleNamespace(returncode=0,stdout=output,stderr='')):
      with self.assertRaises((ValueError,RuntimeError)) as error:provider('brief',{})
      self.assertNotIn('PRIVATE',str(error.exception))
 def test_cursor_executable_names(self):
  from providers import executable
  with patch('providers.shutil.which',side_effect=lambda name:'/fixture/agent' if name=='agent' else None),patch('providers.Path.is_file',return_value=False):
   self.assertEqual(executable('cursor'),'/fixture/agent')
 def test_new_agent_invocation_policy_follows_destination(self):
  with tempfile.TemporaryDirectory() as tmp:
   generate=lambda *_:{'skill_md':'---\nname: policy-test\ndescription: Use for verification.\n---\nCheck the result.'}
   manager=Manager(Path(tmp)/'shared',generate,Path(tmp)/'state');self.addCleanup(manager.temporary.cleanup)
   preview=manager.create(dict(brief='Check a result',target='cursor',explicit=True))
   self.assertIn('disable-model-invocation: true',preview['candidates'][0]['content'])
   with self.assertRaisesRegex(ValueError,'explicit-only'):manager.create(dict(brief='Check a result',target='opencode',explicit=True))
 def test_claude_structured_output_and_login_environment(self):
  with tempfile.TemporaryDirectory() as tmp:
   p=AuthorProvider(Path(tmp)/'settings.json');p.name='claude'
   with patch('providers.executable',return_value='/test/claude'), patch.dict('os.environ',{'ANTHROPIC_API_KEY':'dummy'}), patch('providers.subprocess.run',return_value=SimpleNamespace(returncode=0,stdout=json.dumps({'structured_output':{'skill_md':'example'}}),stderr='')) as run:
    self.assertEqual(p('brief',{}),{'skill_md':'example'})
    args,kw=run.call_args;self.assertIn('--json-schema',args[0]);self.assertEqual(args[0][args[0].index('--tools')+1],'');self.assertNotIn('ANTHROPIC_API_KEY',kw['env'])
 def test_claude_errors_and_missing_output(self):
  with tempfile.TemporaryDirectory() as tmp:
   p=AuthorProvider(Path(tmp)/'settings.json');p.name='claude'
   with patch('providers.executable',return_value='/test/claude'),patch('providers.subprocess.run',return_value=SimpleNamespace(returncode=0,stdout='{"is_error":true,"result":"No login"}',stderr='')):
    with self.assertRaises(RuntimeError):p('brief',{})
   with patch('providers.executable',return_value=None):
    with self.assertRaises(RuntimeError):p('brief',{})
 def test_provider_setting_and_invalid_choice(self):
  with tempfile.TemporaryDirectory() as tmp:
   settings=Path(tmp)/'settings.json';p=AuthorProvider(settings)
   with patch('providers.executable',return_value='/test/claude'):p.select('claude')
   self.assertEqual(AuthorProvider(settings).name,'claude')
   with self.assertRaises(ValueError):p.select('unknown')
 def test_claude_create_sets_invocation_metadata(self):
  with tempfile.TemporaryDirectory() as tmp:
   root=Path(tmp)/'.claude/skills';root.mkdir(parents=True)
   m=Manager(root,lambda p,s:{'skill_md':'---\nname: demo-test\ndescription: Use for testing.\n---\nWrite a result.'},Path(tmp)/'state')
   draft=m.create({'brief':'Test a skill','explicit':True})
   self.assertIn('disable-model-invocation: true',draft['candidates'][0]['content'])
   self.assertTrue(m.conflict('synced'));m.temporary.cleanup()
class RecommendationProviderTests(unittest.TestCase):
 def test_analysis_uses_selected_agent_without_changing_authoring_preference(self):
  with tempfile.TemporaryDirectory() as tmp:
   p=AuthorProvider(Path(tmp)/'settings.json');p.name='codex'
   with patch('providers.executable',return_value='/test/claude'),patch('providers.subprocess.run',return_value=SimpleNamespace(returncode=0,stdout=json.dumps({'structured_output':{'summary':'ok','recommendations':[]}}),stderr='')) as run:
    result=p.generate('reviewed sample',{},provider='claude',analysis=True)
    args,kwargs=run.call_args
    self.assertEqual(p.name,'codex');self.assertEqual(result['summary'],'ok')
    self.assertIn('--strict-mcp-config',args[0]);self.assertIn('--setting-sources',args[0]);self.assertIn('--no-session-persistence',args[0])
    self.assertEqual(kwargs['input'],'reviewed sample');self.assertEqual(args[0][args[0].index('--tools')+1],'')
 def test_codex_analysis_is_ephemeral_and_disables_inherited_tools(self):
  with tempfile.TemporaryDirectory() as tmp:
   p=AuthorProvider(Path(tmp)/'settings.json')
   def complete(cmd,**kwargs):
    Path(cmd[cmd.index('-o')+1]).write_text('{"summary":"ok","recommendations":[]}')
    return SimpleNamespace(returncode=0,stdout='',stderr='')
   with patch('providers.executable',return_value='/test/codex'),patch('providers.subprocess.run',side_effect=complete) as run:
    p.generate('reviewed sample',{},provider='codex',analysis=True)
    cmd=run.call_args.args[0]
    self.assertIn('--ignore-user-config',cmd);self.assertIn('--ephemeral',cmd)
    self.assertIn('web_search="disabled"',cmd)
    self.assertEqual(cmd[cmd.index('--sandbox')+1],'read-only')
    disabled=[cmd[i+1] for i,value in enumerate(cmd) if value=='--disable']
    for feature in ['shell_tool','apps','plugins','hooks','multi_agent']:self.assertIn(feature,disabled)
 def test_analysis_error_does_not_echo_provider_output(self):
  with tempfile.TemporaryDirectory() as tmp:
   p=AuthorProvider(Path(tmp)/'settings.json')
   with patch('providers.executable',return_value='/test/codex'),patch('providers.subprocess.run',return_value=SimpleNamespace(returncode=1,stdout='',stderr='PRIVATE USAGE CONTENT')):
    with self.assertRaises(RuntimeError) as raised:p.generate('sample',{},provider='codex',analysis=True)
    self.assertNotIn('PRIVATE',str(raised.exception))
   with patch('providers.executable',return_value='/test/claude'),patch('providers.subprocess.run',return_value=SimpleNamespace(returncode=0,stdout=json.dumps({'is_error':True,'result':'PRIVATE USAGE CONTENT'}),stderr='')):
    with self.assertRaises(RuntimeError) as raised:p.generate('sample',{},provider='claude',analysis=True)
    self.assertNotIn('PRIVATE',str(raised.exception))

if __name__=='__main__':unittest.main()

class AdditionalProviderTests(unittest.TestCase):
 def setUp(self):
  patcher=patch('providers.opencode_support.capabilities',return_value={'standalone':True,'compatible':True});patcher.start();self.addCleanup(patcher.stop)
 def test_opencode_combines_text_events_without_tool_output(self):
  with tempfile.TemporaryDirectory() as tmp:
   provider=AuthorProvider(Path(tmp)/'settings.json')
   output='\n'.join(map(json.dumps,[{'type':'step_start'},{'type':'text','part':{'text':'{"skill_md":'}},{'type':'tool_result','part':{'text':'PRIVATE TOOL'}},{'type':'text','part':{'text':'"result"}'}},{'type':'step_finish'}]))
   with patch('providers.executable',return_value='/fixture/opencode'),patch('providers.subprocess.run',return_value=SimpleNamespace(returncode=0,stdout=output,stderr='')):
    self.assertEqual(provider.generate('brief',{},provider='opencode'),{'skill_md':'result'})
 def test_no_inherited_api_key_overrides(self):
  with tempfile.TemporaryDirectory() as tmp:
   provider=AuthorProvider(Path(tmp)/'settings.json')
   with patch.dict('os.environ',{'CURSOR_API_KEY':'PRIVATE','OPENAI_API_KEY':'PRIVATE','DEEPSEEK_API_KEY':'PRIVATE'}),patch('providers.executable',return_value='/fixture/cursor'),patch('providers.subprocess.run',return_value=SimpleNamespace(returncode=0,stdout='{"subtype":"success","result":"{}"}',stderr='')) as run:
    provider.generate('brief',{},provider='cursor')
    for key in ['CURSOR_API_KEY','OPENAI_API_KEY','DEEPSEEK_API_KEY']:self.assertNotIn(key,run.call_args.kwargs['env'])
 def test_model_settings_are_validated_on_load_and_save(self):
  with tempfile.TemporaryDirectory() as tmp:
   settings=Path(tmp)/'settings.json';settings.write_text(json.dumps({'provider':'opencode','models':{'opencode':'broken','unknown':'private','cursor':{'key':'private'}}}))
   provider=AuthorProvider(settings);self.assertEqual(provider.models,{})
   with patch('providers.executable',return_value='/fixture/opencode'):
    with self.assertRaisesRegex(ValueError,'provider/model'):provider.select('opencode','missing-provider')
    provider.select('opencode','provider/model');provider.select('opencode','');self.assertEqual(provider.models['opencode'],'')
