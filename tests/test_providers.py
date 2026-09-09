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
if __name__=='__main__':unittest.main()
