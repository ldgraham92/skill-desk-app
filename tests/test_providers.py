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
