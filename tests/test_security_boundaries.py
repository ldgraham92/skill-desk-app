"""Security boundary regressions using only synthetic requests and temporary files."""
import ast
import io
import json
import os
from pathlib import Path
import secrets
import sys
import tempfile
import threading
from types import SimpleNamespace
import unittest
from unittest.mock import Mock, patch
from urllib.parse import unquote, urlsplit

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT/'scripts'))
import skill_desk
from nearby import receiver_address, Session, Nearby
from projects import Projects, project_destination


def handler_method(name, namespace):
    tree = ast.parse((ROOT/'scripts/skill_desk.py').read_text())
    serve = next(n for n in tree.body if isinstance(n, ast.FunctionDef) and n.name == 'serve')
    handler = next(n for n in serve.body if isinstance(n, ast.ClassDef) and n.name == 'Handler')
    method = next(n for n in handler.body if isinstance(n, ast.FunctionDef) and n.name == name)
    exec(compile(ast.Module(body=[method], type_ignores=[]), str(ROOT/'scripts/skill_desk.py'), 'exec'), namespace)
    return namespace[name]


class Response:
    def __init__(self, path, headers=None, payload=None):
        self.path = path
        self.headers = {'Host': '127.0.0.1:12345', **(headers or {})}
        self.wfile = io.BytesIO()
        self.rfile = io.BytesIO(json.dumps(payload or {}).encode())
        self.status = None

    def send_response(self, status): self.status = status
    def send_error(self, status): self.status = status
    def send_header(self, *args): pass
    def end_headers(self): pass
    def json_reply(self, status, value): self.status = status; self.value = value


class SecurityBoundaryTests(unittest.TestCase):
    def test_assets_use_exact_routes_and_reject_link_escape(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            (root/'web/walkthrough').mkdir(parents=True)
            (root/'web/manage.js').write_bytes(b'// fixture')
            (root/'private.txt').write_bytes(b'PRIVATE_SENTINEL')
            with patch.object(skill_desk, 'PROJECT', root):
                self.assertEqual(skill_desk.web_asset('/manage.js'), (b'// fixture', 'text/javascript'))
                for route in ('/../private.txt', '/walkthrough/../../private.txt', '//private.txt', str(root/'private.txt')):
                    with self.subTest(route=route), self.assertRaises(KeyError):
                        skill_desk.web_asset(route)
                (root/'web/walkthrough/library.png').symlink_to(root/'private.txt')
                with self.assertRaises(OSError): skill_desk.web_asset('/walkthrough/library.png')

    def test_http_asset_routes_reject_decoded_traversal_and_bad_host(self):
        get = handler_method('do_GET', dict(port=12345, unquote=unquote, urlsplit=urlsplit,
                             WEB_ASSETS=skill_desk.WEB_ASSETS, web_asset=skill_desk.web_asset))
        for route in ('/%2e%2e/private.txt', '/walkthrough/%2e%2e/%2e%2e/private.txt',
                      '/walkthrough/library.png%00', '/%252e%252e/private.txt', '/etc/passwd'):
            with self.subTest(route=route):
                response = Response(route)
                get(response)
                self.assertEqual(response.status, 404)
                self.assertEqual(response.wfile.getvalue(), b'')
        response = Response('/manage.js', {'Host': 'untrusted.example:12345'})
        get(response)
        self.assertEqual(response.status, 403)

    def test_project_registration_requires_same_origin_and_control_token(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            repo = root/'selected repository'; repo.mkdir(); (repo/'.git').mkdir()
            projects = Projects(root/'state')
            manager = SimpleNamespace(lock=threading.RLock(), busy=False, drafts={})
            catalog = SimpleNamespace(refresh=Mock(), notify=Mock(), roots=[])
            post = handler_method('handle_post', dict(port=12345, token='fixture-token', secrets=secrets,
                json=json, urlsplit=urlsplit, manager=manager, UPDATE_GATE=SimpleNamespace(pending=False),
                projects=projects, catalog=catalog, global_roots=[], changed=threading.Event(), os=os))
            payload = {'path': str(repo), 'name': 'Synthetic repository'}
            headers = {'Origin': 'http://127.0.0.1:12345', 'X-Skill-Desk-Token': 'fixture-token',
                       'Content-Type': 'application/json', 'Content-Length': str(len(json.dumps(payload).encode()))}
            for override in ({'Origin': 'https://untrusted.example'}, {'X-Skill-Desk-Token': ''},
                             {'Host': 'untrusted.example:12345'}, {'Origin': 'null'}):
                response = Response('/api/project-add', {**headers, **override}, payload)
                post(response)
                self.assertEqual(response.status, 403)
                self.assertEqual(projects.listing(), [])
            response = Response('/api/project-add', headers, payload)
            post(response)
            self.assertEqual(response.status, 200, response.value)
            self.assertEqual(projects.listing()[0]['path'], str(repo.resolve()))
            self.assertEqual(list(repo.iterdir()), [repo/'.git'])
            (repo/'.agents').symlink_to(root/'state', target_is_directory=True)
            with self.assertRaises(ValueError): project_destination(repo, 'codex')

    def test_receiver_address_rejects_unbounded_and_non_string_input_before_parsing(self):
        class Untrusted:
            def __str__(self): raise AssertionError('Must not stringify arbitrary values')
        with patch('nearby.local_ip', side_effect=AssertionError('Must reject before IP parsing')):
            for value in ('.'*350000, ' '*350000+'127.0.0.1:1', Untrusted(), None, {}):
                with self.assertRaises(ValueError): receiver_address(value)
        for value in ('8.8.8.8:1', '127.0.0.1:0', '127.0.0.1:65536', '127.0.0.1:123456',
                      '127.0.0.1:+1', '127.0.0.1:１２', '127.0.0.1:1:2', 'example.com:80', '::1:80'):
            with self.subTest(value=value), self.assertRaises(ValueError): receiver_address(value)
        self.assertEqual(receiver_address(' 192.168.1.2:53317 '), ('192.168.1.2', 53317))
        self.assertEqual(receiver_address('127.0.0.1:1'), ('127.0.0.1', 1))

    def test_invalid_probe_does_not_open_a_connection_and_sharing_starts_inactive(self):
        session = Session.__new__(Session)
        session.connection = Mock(side_effect=AssertionError('Invalid address must not connect'))
        with self.assertRaises(ValueError): session.probe('.'*350000)
        session.connection.assert_not_called()
        with patch('nearby.Session') as constructor:
            nearby = Nearby()
            self.assertFalse(nearby.active)
            constructor.assert_not_called()
