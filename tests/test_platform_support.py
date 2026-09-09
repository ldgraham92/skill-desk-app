import os
from pathlib import Path
import subprocess
import sys
import tempfile
import unittest
from unittest.mock import patch
sys.path.insert(0, str(Path(__file__).resolve().parents[1]/'scripts'))
import platform_support as support

class PlatformTests(unittest.TestCase):
    def test_windows_paths_respect_local_appdata(self):
        with tempfile.TemporaryDirectory() as tmp, patch.object(sys, 'platform', 'win32'), patch.dict(os.environ, {'LOCALAPPDATA': tmp}, clear=True), patch('platform_support.Path.home', side_effect=RuntimeError('No home directory')):
            self.assertEqual(support.data_dir(), Path(tmp)/'Skill-Desk')
            self.assertEqual(support.cache_dir(), Path(tmp)/'Skill-Desk/Cache')
    def test_linux_paths_respect_xdg(self):
        with patch.object(sys, 'platform', 'linux'), patch.dict(os.environ, {'XDG_DATA_HOME':'/tmp/data','XDG_CACHE_HOME':'/tmp/cache'}, clear=True), patch('platform_support.Path.home', side_effect=RuntimeError('No home directory')):
            self.assertEqual(support.data_dir(), Path('/tmp/data/Skill-Desk'))
            self.assertEqual(support.cache_dir(), Path('/tmp/cache/Skill-Desk'))
    def test_lock_excludes_second_process_and_releases(self):
        with tempfile.TemporaryDirectory() as tmp:
            target=Path(tmp)/'sync.lock'
            code='from platform_support import lock_file; import sys; lock=lock_file(sys.argv[1])'
            env=dict(os.environ,PYTHONPATH=str(Path(support.__file__).parent))
            handle=support.lock_file(target)
            result=subprocess.run([sys.executable,'-c',code,str(target)],env=env,capture_output=True)
            self.assertNotEqual(result.returncode,0)
            handle.close()
            result=subprocess.run([sys.executable,'-c',code,str(target)],env=env,capture_output=True)
            self.assertEqual(result.returncode,0,result.stderr)
    def test_windows_npm_shim_bypasses_shell(self):
        with tempfile.TemporaryDirectory() as tmp:
            folder=Path(tmp); entry=folder/'node_modules/@openai/codex/bin/codex.js'
            entry.parent.mkdir(parents=True);entry.write_text('test')
            with patch.object(sys,'platform','win32'), patch('platform_support.shutil.which',return_value='node.exe'):
                self.assertEqual(support.command_prefix(str(folder/'codex.cmd')), ['node.exe',str(entry)])
                with self.assertRaises(RuntimeError):support.command_prefix(str(folder/'unknown.cmd'))
