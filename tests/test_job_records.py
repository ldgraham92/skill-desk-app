"""Offline job persistence and API recovery tests using synthetic data only."""
import ast
from copy import deepcopy
import io
import json
from pathlib import Path
import sys
import tempfile
import time
import unittest
from unittest.mock import patch
from urllib.parse import unquote, urlsplit

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT/'scripts'))
from management import Manager
from recommendations import Recommendations


class JobRecordTests(unittest.TestCase):
    def setUp(self):
        temp = tempfile.TemporaryDirectory()
        self.addCleanup(temp.cleanup)
        self.base = Path(temp.name)
        self.manager = self.new_manager()
        self.request = dict(provider='codex', target='codex', days=30, installed=['existing'],
                            excerpts=[dict(id='prompt-3', text='PRIVATE_EXCERPT')])
        self.item = dict(skill='fixture:debug', reason='Useful.', firstStep='Check it.', evidence=['prompt-3'])
        self.output = dict(summary='Synthetic summary.', recommendations=[self.item], covered=[])
        self.service = Recommendations(ROOT, lambda *_: self.output)
        self.service.candidates = lambda _: {'fixture:debug': dict(id='fixture:debug', name='debug')}

    def new_manager(self):
        manager = Manager(self.base/'skills', None, self.base/'state')
        self.addCleanup(manager.temporary.cleanup)
        return manager

    def run_job(self, task, action='recommend'):
        token = self.manager.job(action, self.request, task)['job']
        deadline = time.monotonic()+3
        while self.manager.busy and time.monotonic() < deadline:
            time.sleep(.005)
        self.assertFalse(self.manager.busy, 'Synthetic job did not finish')
        return token

    def get(self, manager, token):
        # Execute the actual HTTP method without starting the application/server.
        tree = ast.parse((ROOT/'scripts/skill_desk.py').read_text())
        serve = next(n for n in tree.body if isinstance(n, ast.FunctionDef) and n.name == 'serve')
        handler = next(n for n in serve.body if isinstance(n, ast.ClassDef) and n.name == 'Handler')
        method = next(n for n in handler.body if isinstance(n, ast.FunctionDef) and n.name == 'do_GET')
        namespace = dict(manager=manager, port=12345, json=json, time=time, unquote=unquote, urlsplit=urlsplit)
        exec(compile(ast.Module(body=[method], type_ignores=[]), str(ROOT/'scripts/skill_desk.py'), 'exec'), namespace)
        class Response:
            headers = {'Host': '127.0.0.1:12345'}
            path = '/api/jobs/'+token
            wfile = io.BytesIO()
            def send_response(self, status): self.status = status
            def send_error(self, status): self.status = status
            def send_header(self, *args): pass
            def end_headers(self): pass
        response = Response()
        namespace['do_GET'](response)
        return response.status, json.loads(response.wfile.getvalue()) if response.wfile.getvalue() else None

    def test_validator_failures_keep_allowlisted_code_and_original_stage(self):
        base = deepcopy(self.output)
        cases = [
            ('invalid_summary', dict(base, summary='')),
            ('invalid_recommendations', dict(base, recommendations=None)),
            ('unknown_skill', dict(base, recommendations=[dict(self.item, skill='PRIVATE_SKILL')])),
            ('duplicate_recommendation', dict(base, recommendations=[self.item, self.item])),
            ('invalid_reason', dict(base, recommendations=[dict(self.item, reason='')])),
            ('invalid_evidence_count', dict(base, recommendations=[dict(self.item, evidence=[])])),
            ('invalid_evidence_count', dict(base, recommendations=[dict(self.item, evidence=['prompt-3']*4)])),
            ('unknown_evidence_id', dict(base, recommendations=[dict(self.item, evidence=['PRIVATE_CITATION'])])),
            ('unknown_evidence_id', dict(base, recommendations=[dict(self.item, evidence=[{}])])),
            ('invalid_first_step', dict(base, recommendations=[dict(self.item, firstStep=' ')])),
            ('invalid_covered', dict(base, covered=None)),
            ('unknown_covered_skill', dict(base, covered=[dict(self.item, installed='PRIVATE_INSTALLED')])),
            ('invalid_covered_item', dict(base, covered=[dict(self.item, installed='existing')])),
        ]
        for index, (code, output) in enumerate(cases):
            with self.subTest(code=code, case=index):
                self.output = output
                token = self.run_job(self.service.run)
                row = self.manager.job_records.value[token]
                self.assertEqual(row['status'], 'failed')
                self.assertEqual(row.get('failure_code'), code)
                self.assertEqual(row.get('failure_stage'), 'validating')
                self.assertEqual(set(row), {'action', 'status', 'finished_at', 'failure_code', 'failure_stage'})
                self.assertEqual(self.manager.jobs[token]['phase'], 'failed')
                saved = self.get(self.new_manager(), token)[1]
                self.assertEqual(saved['failure_code'], code)
                self.assertEqual(saved['failure_stage'], 'validating')
        self.assertNotIn('PRIVATE', (self.base/'state/job-records.json').read_text())

    def test_unknown_exceptions_and_stages_do_not_persist_arbitrary_text(self):
        for stage, expected_stage in [(None, 'preparing'), ('generating', 'generating'), ('PRIVATE_STAGE', 'unknown')]:
            def task(payload, progress):
                if stage: progress(stage, 'PRIVATE_PROGRESS')
                error = ValueError('PRIVATE_EXCEPTION')
                error.code = 'unknown_evidence_id'  # Arbitrary exceptions cannot impersonate validation failures.
                raise error
            token = self.run_job(task)
            row = self.manager.job_records.value[token]
            self.assertEqual(row.get('failure_code'), 'unknown')
            self.assertEqual(row.get('failure_stage'), expected_stage)
        self.assertNotIn('PRIVATE', (self.base/'state/job-records.json').read_text())

    def test_saved_failure_fields_are_allowlisted_when_read(self):
        self.manager.job_records.save({'old': dict(action='recommend', status='failed', finished_at=100,
            failure_code=['PRIVATE_CODE'], failure_stage='PRIVATE_STAGE', message='PRIVATE_EXCEPTION', result='PRIVATE_RESULT')})
        row = self.get(self.new_manager(), 'old')[1]
        self.assertEqual(row['failure_code'], 'unknown')
        self.assertEqual(row['failure_stage'], 'unknown')
        self.assertNotIn('PRIVATE', json.dumps(row))

    def test_malformed_saved_job_keeps_app_available_without_replay_or_overwrite(self):
        records={'bad':None,'running':dict(action='recommend',status='running')}
        self.manager.job_records.save(records)
        path=self.base/'state/job-records.json';before=path.read_bytes()
        reloaded=self.new_manager()
        self.assertIn('invalid structure',reloaded.job_records.error)
        self.assertEqual(reloaded.interrupted_jobs,[])
        self.assertIsNone(reloaded.job_status('bad'))
        task=unittest.mock.Mock()
        with self.assertRaisesRegex(ValueError,'preserved'):reloaded.job('recommend',{},task)
        task.assert_not_called()
        self.assertFalse(reloaded.busy)
        self.assertEqual(path.read_bytes(),before)

    def test_other_actions_keep_the_existing_minimal_record(self):
        def task(*_): raise ValueError('PRIVATE_EXCEPTION')
        token = self.run_job(task, action='create')
        row = self.manager.job_records.value[token]
        self.assertEqual(set(row), {'action', 'status', 'finished_at'})
        self.assertEqual(row['status'], 'failed')

    def test_saved_outcomes_legacy_failure_and_missing_job(self):
        records = {status: dict(action='recommend', status=status, finished_at=100)
                   for status in ('complete', 'failed', 'cancelled')}
        records['running'] = dict(action='recommend', status='running', started_at=90)
        self.manager.job_records.save(records)
        reloaded = self.new_manager()
        for saved_status in records:
            with self.subTest(status=saved_status):
                http, row = self.get(reloaded, saved_status)
                self.assertEqual(http, 200)
                self.assertEqual(row['status'], 'failed' if saved_status == 'running' else saved_status)
                self.assertEqual(row['phase'], 'interrupted' if saved_status == 'running' else 'ready' if saved_status == 'complete' else saved_status)
                self.assertIs(row.get('resultAvailable'), False)
                self.assertNotIn('result', row)
                if saved_status == 'failed':
                    self.assertEqual(row['failure_code'], 'unknown')
                    self.assertEqual(row['failure_stage'], 'unknown')
                    self.assertIn('unknown', row['message'])
        self.assertEqual(self.get(reloaded, 'missing')[0], 404)

    def test_same_session_eviction_preserves_completion_without_private_result(self):
        token = self.run_job(lambda *_: dict(text='PRIVATE_RESULT'))
        self.assertEqual(self.get(self.manager, token)[1]['result']['text'], 'PRIVATE_RESULT')
        del self.manager.jobs[token]
        row = self.get(self.manager, token)[1]
        self.assertEqual(row['status'], 'complete')
        self.assertIs(row.get('resultAvailable'), False)
        self.assertNotIn('previous', row['message'])
        self.assertNotIn('PRIVATE', json.dumps(row))

    def test_failed_record_write_remains_best_effort_without_leaking_input(self):
        save = self.manager.job_records.save
        def fail_terminal(records):
            if any(row['status'] != 'running' for row in records.values()):
                raise OSError('PRIVATE_DISK_ERROR')
            return save(records)
        with patch.object(self.manager.job_records, 'save', side_effect=fail_terminal):
            token = self.run_job(lambda *_: {'text': 'PRIVATE_RESULT'})
        self.assertEqual(self.manager.jobs[token]['status'], 'complete')
        self.assertEqual(self.manager.job_records.value[token]['status'], 'running')
        self.assertNotIn('PRIVATE', (self.base/'state/job-records.json').read_text())
