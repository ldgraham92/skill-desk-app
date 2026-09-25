from datetime import datetime, timezone
from contextlib import closing
import hashlib
import json
from pathlib import Path
import sqlite3
import sys
import tempfile
import time
import unittest
from unittest.mock import patch

ROOT=Path(__file__).resolve().parent.parent
sys.path.insert(0,str(ROOT/'scripts'))
from usage_history import scan, redact, sources, project_matches
from recommendations import Recommendations
from management import Manager
from skill_packages import import_package
import bundled_collections


class UsageTests(unittest.TestCase):
    def setUp(self):
        self.tmp=tempfile.TemporaryDirectory();self.addCleanup(self.tmp.cleanup)
        self.base=Path(self.tmp.name);self.roots={name:self.base/name for name in ['codex','claude','opencode']}
        self.now=time.time();self.iso=datetime.fromtimestamp(self.now,timezone.utc).isoformat()

    def jsonl(self,path,rows):
        path.parent.mkdir(parents=True,exist_ok=True);path.write_text('\n'.join(json.dumps(r) for r in rows)+'\n',encoding='utf-8')

    def test_coverage_distinguishes_missing_corrupt_and_delegated_sessions(self):
        empty=scan(['codex'],30,self.roots,self.now)
        self.assertEqual(empty['coverage']['codex']['status'],'missing')
        self.jsonl(self.roots['codex']/'sessions/human.jsonl',[
            dict(type='session_meta',payload=dict(source='vscode',cwd='/workspace/my-project')),
            dict(timestamp=self.iso,type='event_msg',payload=dict(type='user_message',message='Review this application history reader'))])
        self.jsonl(self.roots['codex']/'archived_sessions/agent.jsonl',[
            dict(type='session_meta',payload=dict(source={'subagent':{}}))])
        self.jsonl(self.roots['codex']/'sessions/broken.jsonl',[])
        (self.roots['codex']/'sessions/broken.jsonl').write_text('{broken')
        sample=scan(['codex'],30,self.roots,self.now)
        coverage=sample['coverage']['codex']
        self.assertEqual(coverage['sessionsFound'],3)
        self.assertEqual(coverage['sessionsScanned'],2)
        self.assertEqual(coverage['sessionsSkipped'],1)
        self.assertEqual(coverage['subagentSessions'],1)
        self.assertEqual(coverage['budgetSkippedSessions'],0)
        self.assertEqual(coverage['sessionsIncluded'],1)
        self.assertEqual(coverage['malformedRecords'],1)
        self.assertEqual(sample['excerpts'][0]['project'],'my-project')
        self.assertEqual(sample['checkedAt'],self.now)
        self.assertNotIn('/workspace',json.dumps(sample))

    def test_sample_balances_projects_and_dates(self):
        for project,count in [('busy',30),('quiet',2)]:
            self.jsonl(self.roots['codex']/f'sessions/{project}.jsonl',[
                dict(type='session_meta',payload=dict(cwd='/workspace/'+project)),
                *[dict(timestamp=self.now-(i%2)*86400,type='event_msg',payload=dict(type='user_message',message=f'Review module {i} for {project}')) for i in range(count)]])
        with patch('usage_history.MAX_EXCERPTS',4):sample=scan(['codex'],30,self.roots,self.now)
        self.assertEqual({e['project'] for e in sample['excerpts']},{'busy','quiet'})
        self.assertEqual(len({e['date'] for e in sample['excerpts']}),2)
        self.assertEqual(sum(e['project']=='quiet' for e in sample['excerpts']),2)
        self.assertTrue(sample['partial'])

    def test_codex_desktop_response_items_include_only_user_requests(self):
        def message(role,text):return dict(timestamp=self.iso,type='response_item',payload=dict(type='message',role=role,content=[dict(type='input_text',text=text)]))
        self.jsonl(self.roots['codex']/'sessions/desktop.jsonl',[
            dict(type='session_meta',payload=dict(source='vscode',cwd=str(self.base/'repo'))),
            message('user','<recommended_plugins>PRIVATE PLUGIN LIST</recommended_plugins><environment_context>PRIVATE ENVIRONMENT</environment_context>'),
            message('user','# AGENTS.md instructions for /private/project\nPRIVATE INJECTED INSTRUCTIONS'),
            message('user','Diagnose my failing desktop history reader'),
            message('user','Inspect this desktop-only user message'),
            message('assistant','PRIVATE ASSISTANT RESPONSE'),
            message('developer','PRIVATE DEVELOPER INSTRUCTIONS'),
            dict(timestamp=self.iso,type='event_msg',payload=dict(type='user_message',message='Diagnose my failing desktop history reader'))])
        sample=scan(['codex'],30,self.roots,self.now,project_path=str(self.base/'repo'))
        self.assertEqual(sample['sampled'],2)
        self.assertEqual({e['text'] for e in sample['excerpts']},{'Diagnose my failing desktop history reader','Inspect this desktop-only user message'})
        self.assertNotIn('PRIVATE',json.dumps(sample))

    def test_subagent_sessions_do_not_exhaust_budget_before_human_history(self):
        for i in range(5):
            self.jsonl(self.roots['codex']/f'sessions/subagent-{i}.jsonl',[
                dict(type='session_meta',payload=dict(source={'subagent':{'thread_spawn':{}}})),
                dict(type='padding',text='x'*10000),
                dict(timestamp=self.iso,type='event_msg',payload=dict(type='user_message',message='PRIVATE DELEGATED TASK'))])
        self.jsonl(self.roots['codex']/'sessions/human.jsonl',[
            dict(type='session_meta',payload=dict(source='vscode')),
            dict(timestamp=self.iso,type='response_item',payload=dict(type='message',role='user',content=[dict(type='input_text',text='Review my recurring application failures')]))])
        import os
        os.utime(self.roots['codex']/'sessions/human.jsonl',(self.now-5,self.now-5))
        with patch('usage_history.MAX_SCAN_BYTES',2000):sample=scan(['codex'],30,self.roots,self.now)
        self.assertEqual(sample['sampled'],1)
        self.assertNotIn('PRIVATE',json.dumps(sample))

    def test_codex_and_claude_only_recent_user_text_and_deduplicate(self):
        self.jsonl(self.roots['codex']/'history.jsonl',[dict(ts=self.now,text='Diagnose flaky database tests'),dict(ts=self.now-100*86400,text='Old unrelated prompt')])
        self.jsonl(self.roots['codex']/'sessions/2026/rollout.jsonl',[
            dict(timestamp=self.iso,type='event_msg',payload=dict(type='user_message',message='Diagnose flaky database tests')),
            dict(timestamp=self.iso,type='event_msg',payload=dict(type='agent_message',message='PRIVATE ASSISTANT REPLY')),
            dict(timestamp=self.iso,type='response_item',payload=dict(type='function_call_output',output='PRIVATE TOOL OUTPUT')),
            dict(timestamp=self.iso,type='event_msg',payload=dict(type='user_message',message='Find a regression in /Users/example/private/code using api_key=supersecret'))])
        self.jsonl(self.roots['claude']/'projects/project/session.jsonl',[
            dict(timestamp=self.iso,type='user',message=dict(content=[dict(type='text',text='Review the React component design'),dict(type='tool_result',content='PRIVATE TOOL CONTENT')])),
            dict(timestamp=self.iso,type='assistant',message=dict(content='PRIVATE RESPONSE')),
            dict(timestamp=self.iso,type='user',isMeta=True,message=dict(content='PRIVATE CONTEXT'))])
        sample=scan(['codex','claude'],30,self.roots,self.now)
        self.assertEqual(sample['sampled'],3)
        encoded=json.dumps(sample)
        for secret in ['PRIVATE','supersecret','/Users/example','Old unrelated']:self.assertNotIn(secret,encoded)
        self.assertIn('[local path]',encoded)

    def test_opencode_both_sqlite_formats_read_only(self):
        root=self.roots['opencode'];root.mkdir()
        path=root/'opencode.db'
        with closing(sqlite3.connect(path)) as db:
            db.executescript('CREATE TABLE message(id TEXT,time_created INTEGER,data TEXT);CREATE TABLE part(message_id TEXT,data TEXT);CREATE TABLE session_message(type TEXT,time_created INTEGER,data TEXT);')
            db.executemany('INSERT INTO message VALUES(?,?,?)',[('u',self.now*1000,'{"role":"user"}'),('a',self.now*1000,'{"role":"assistant"}')])
            db.executemany('INSERT INTO part VALUES(?,?)',[('u','{"type":"text","text":"Help me write better regression tests"}'),('a','{"type":"text","text":"PRIVATE ASSISTANT"}'),('u','{"type":"tool","text":"PRIVATE TOOL"}'),('u','{"type":"text","synthetic":true,"text":"PRIVATE SYNTHETIC"}')])
            db.execute('INSERT INTO session_message VALUES(?,?,?)',('user',self.now*1000,'{"text":"Plan the architecture of this application"}'))
            db.commit()
        digest=hashlib.sha256(path.read_bytes()).hexdigest()
        connections=[];connect=sqlite3.connect
        def capture(*args,**kwargs):
            connection=connect(*args,**kwargs);connections.append(connection);return connection
        with patch('usage_history.sqlite3.connect',side_effect=capture):
            sample=scan(['opencode'],30,self.roots,self.now)
        self.assertEqual(len(connections),1)
        with self.assertRaises(sqlite3.ProgrammingError):connections[0].execute('SELECT 1')
        self.assertEqual(sample['sampled'],2);self.assertNotIn('PRIVATE',json.dumps(sample))
        self.assertEqual(hashlib.sha256(path.read_bytes()).hexdigest(),digest)

    def test_legacy_opencode_and_broken_history(self):
        root=self.roots['opencode'];(root/'storage/message/session').mkdir(parents=True);(root/'storage/part/msg1').mkdir(parents=True)
        (root/'storage/message/session/message.json').write_text(json.dumps(dict(id='msg1',role='user',time={'created':self.now*1000})))
        (root/'storage/part/msg1/part.json').write_text('{"type":"text","text":"Explain this complicated type system"}')
        self.jsonl(self.roots['claude']/'history.jsonl',[dict(timestamp=self.now*1000,display='Write a repeatable verification checklist')])
        with (self.roots['claude']/'history.jsonl').open('a') as f:f.write('{truncated')
        sample=scan(['opencode','claude'],30,self.roots,self.now)
        self.assertEqual(sample['sampled'],2)
        with self.assertRaises(ValueError):scan(['anything'],30,self.roots,self.now)
        with self.assertRaises(ValueError):scan(['codex'],999,self.roots,self.now)

    def test_sample_is_bounded_and_symlink_file_is_not_read(self):
        self.jsonl(self.roots['codex']/'history.jsonl',[dict(ts=self.now,text='Review module number '+str(i)+' '+('x'*2000)) for i in range(200)])
        sample=scan(['codex'],30,self.roots,self.now)
        self.assertEqual(sample['sampled'],120);self.assertTrue(all(len(e['text'])<=1000 for e in sample['excerpts']))
        private=self.base/'private.jsonl';self.jsonl(private,[dict(timestamp=self.now*1000,display='Should never read this linked file')])
        self.roots['claude'].mkdir();(self.roots['claude']/'history.jsonl').symlink_to(private)
        self.assertEqual(scan(['claude'],30,self.roots,self.now)['sampled'],0)

    def test_masking_and_empty_sources(self):
        self.assertNotIn('alice@example.com',redact('Email alice@example.com and password=private-value'))
        self.assertNotIn('private-value',redact('password=private-value'))
        self.assertFalse(any(s['available'] for s in sources(self.roots)))
        self.assertTrue(scan(['codex'],30,self.roots,self.now)['notes'])

    def test_project_history_excludes_other_and_unknown_repositories(self):
        project=str(self.base/'repo')
        self.jsonl(self.roots['codex']/'history.jsonl',[dict(ts=self.now,text='Unattributed global history prompt')])
        for folder,cwd,text in [('a',project+'/src','Debug this project database problem'),('b',project+'-other','PRIVATE unrelated repository prompt'),('c',None,'PRIVATE unidentified session prompt')]:
            self.jsonl(self.roots['codex']/f'sessions/{folder}.jsonl',[
                dict(type='session_meta',payload=dict(cwd=cwd)),
                dict(timestamp=self.iso,type='event_msg',payload=dict(type='user_message',message=text))])
        self.jsonl(self.roots['claude']/'history.jsonl',[
            dict(timestamp=self.now,project=project,display='Review this project component design'),
            dict(timestamp=self.now,project=project+'-other',display='PRIVATE unrelated Claude prompt')])
        self.jsonl(self.roots['claude']/'projects/session.jsonl',[
            dict(timestamp=self.iso,type='user',cwd=project+'/lib',message=dict(content='Explain this project type system')),
            dict(timestamp=self.iso,type='user',message=dict(content='PRIVATE unknown Claude project'))])
        sample=scan(['codex','claude'],30,self.roots,self.now,project_path=project)
        self.assertEqual(sample['sampled'],3)
        self.assertNotIn('PRIVATE',json.dumps(sample))
        self.assertNotIn('Unattributed global',json.dumps(sample))
        self.assertTrue(any('no identifiable repository' in n for n in sample['notes']))
        self.assertGreater(scan(['codex','claude'],30,self.roots,self.now)['sampled'],3)
        empty=scan(['codex'],30,self.roots,self.now,project_path=str(self.base/'empty'))
        self.assertEqual(empty['sampled'],0)
        self.assertTrue(any('All projects' in n for n in empty['notes']))

    def test_project_paths_and_changed_working_directory(self):
        self.assertTrue(project_matches(r'C:\Work\Repo\src',r'c:\work\repo'))
        self.assertFalse(project_matches(r'C:\Work\Repo-other',r'C:\Work\Repo'))
        self.assertFalse(project_matches(r'D:\Work\Repo',r'C:\Work\Repo'))
        self.assertFalse(project_matches('repo/src',str(self.base/'repo')))
        project=self.base/'repo';nested=project/'nested';nested.mkdir(parents=True);(nested/'.git').mkdir()
        self.assertFalse(project_matches(str(nested),str(project)))
        self.jsonl(self.roots['codex']/'sessions/session.jsonl',[
            dict(type='session_meta',payload=dict(cwd=str(project))),
            dict(timestamp=self.iso,type='event_msg',payload=dict(type='user_message',message='Debug the current repository')),
            dict(type='turn_context',payload=dict(cwd=str(self.base/'another'))),
            dict(timestamp=self.iso,type='event_msg',payload=dict(type='user_message',message='PRIVATE changed repository'))])
        sample=scan(['codex'],30,self.roots,self.now,project_path=str(project))
        self.assertEqual(sample['sampled'],1)
        self.assertNotIn('PRIVATE',json.dumps(sample))

    def test_large_session_windows_include_middle_requests_with_fresh_context(self):
        project=str(self.base/'repo');path=self.roots['codex']/'sessions/large.jsonl';path.parent.mkdir(parents=True)
        header=json.dumps(dict(type='session_meta',payload=dict(cwd=project))).encode()+b'\n'
        middle=b'\n'.join(json.dumps(row).encode() for row in [dict(type='turn_context',payload=dict(cwd=project)),dict(timestamp=self.iso,type='event_msg',payload=dict(type='user_message',message='Review this request in the middle of a large session'))])+b'\n'
        content=header+b'\n'*(500000-len(header))+middle
        path.write_bytes(content+b'\n'*(1200000-len(content)))
        with patch('usage_history.MAX_FILE_BYTES',600000):sample=scan(['codex'],30,self.roots,self.now,project_path=project)
        self.assertEqual(sample['sampled'],1)
        self.assertEqual(sample['coverage']['codex']['bytesRead'],600000)
        self.assertEqual(sample['coverage']['codex']['truncatedFiles'],1)

    def test_truncated_session_does_not_attribute_tail_using_stale_context(self):
        project=str(self.base/'repo')
        path=self.roots['codex']/'sessions/large.jsonl'
        self.jsonl(path,[dict(type='session_meta',payload=dict(cwd=project)),
            dict(type='turn_context',payload=dict(cwd=str(self.base/'other'))),
            dict(type='padding',data='x'*3000),
            dict(timestamp=self.iso,type='event_msg',payload=dict(type='user_message',message='PRIVATE tail with missing context')),
            dict(type='turn_context',payload=dict(cwd=project)),
            dict(timestamp=self.iso,type='event_msg',payload=dict(type='user_message',message='Debug repository with fresh context'))])
        with patch('usage_history.MAX_FILE_BYTES',800):
            sample=scan(['codex'],30,self.roots,self.now,project_path=project)
        self.assertEqual(sample['sampled'],1)
        self.assertNotIn('PRIVATE',json.dumps(sample))
        self.assertTrue(any('truncated' in n for n in sample['notes']))


class RecommendationTests(unittest.TestCase):
    def setUp(self):
        self.tmp=tempfile.TemporaryDirectory();self.addCleanup(self.tmp.cleanup);self.base=Path(self.tmp.name)
        self.roots={k:self.base/k for k in ['codex','claude','opencode']};self.roots['codex'].mkdir()
        (self.roots['codex']/'history.jsonl').write_text(json.dumps(dict(ts=time.time(),text='Help me diagnose this persistent failing test.')))
        self.calls=[]
        def generate(provider,prompt,schema):
            self.calls.append((provider,prompt,schema))
            return dict(summary='Your work often involves debugging.',covered=[],recommendations=[dict(skill='ai-hero:diagnosing-bugs',reason='A repeatable debugging process would help with recurring failures.',firstStep='Investigate the recurring test failure by finding a minimal reproduction.',evidence=['prompt-1'])])
        self.service=Recommendations(ROOT,generate,self.roots)

    def request(self,installed=None):
        preview=self.service.preview(dict(target='codex',days=30))
        edits=[dict(id=e['id'],text='Edited and reviewed debugging task') for e in preview['excerpts']]
        return self.service.prepare(dict(preview=preview['preview'],provider='codex',excerpts=edits),installed or [])

    def test_project_default_and_scope_are_bound_to_review(self):
        project=dict(id='p1',name='Portal',path=str(self.base/'portal'))
        folder=self.roots['codex']/'sessions';folder.mkdir()
        (folder/'session.jsonl').write_text('\n'.join(json.dumps(row) for row in [
            dict(type='session_meta',payload=dict(cwd=project['path'])),
            dict(timestamp=time.time(),type='event_msg',payload=dict(type='user_message',message='Investigate this project failing database tests'))]))
        preview=self.service.preview(dict(target='codex',project=project))
        self.assertEqual(preview['scope'],'project');self.assertEqual(preview['sampled'],1)
        request=self.service.prepare(dict(preview=preview['preview'],provider='codex',scope='all',excerpts=preview['excerpts']),[])
        self.assertEqual(request['scope'],'project')
        self.service.run(request,lambda *a:None)
        self.assertNotIn('persistent failing test',self.calls[-1][1])
        self.assertNotIn(project['path'],self.calls[-1][1])
        self.assertEqual(self.service.preview(dict(target='codex',project=project,scope='all'))['sampled'],2)
        for payload in [dict(target='codex',scope='project'),dict(target='codex',scope='invalid')]:
            with self.assertRaises(ValueError): self.service.preview(payload)

    def test_no_agent_call_until_review_and_only_edited_payload_is_sent(self):
        request=self.request();self.assertEqual(self.calls,[])
        output=self.service.run(request,lambda *args:None)
        self.assertEqual(self.calls[0][0],'codex');self.assertIn('Edited and reviewed',self.calls[0][1]);self.assertNotIn('persistent failing test',self.calls[0][1])
        self.assertEqual(output['recommendations'][0]['name'],'diagnosing-bugs')
        self.assertEqual(output['recommendations'][0]['evidence'][0]['text'],'Edited and reviewed debugging task')

    def test_output_schema_binds_evidence_to_selected_excerpts_per_run(self):
        # Review can remove excerpts without renumbering their IDs.
        (self.roots['codex']/'history.jsonl').write_text('\n'.join(
            json.dumps(dict(ts=time.time()-i,text=f'Diagnose recurring failure number {i}')) for i in range(3)))
        preview=self.service.preview(dict(target='codex',days=30))
        self.service.generate=lambda provider,prompt,schema:self.calls.append((provider,prompt,schema)) or dict(summary='No additions.',recommendations=[],covered=[])
        for selected in ([preview['excerpts'][2]],preview['excerpts'][:2]):
            request=self.service.prepare(dict(preview=preview['preview'],provider='codex',excerpts=selected),[])
            self.service.run(request,lambda *a:None)
        for call,expected in zip(self.calls,[['prompt-3'],['prompt-1','prompt-2']]):
            evidence=call[2]['properties']['recommendations']['items']['properties']['evidence']
            self.assertEqual(evidence['items'].get('enum'),expected)
            payload=json.loads(call[1].split('\n',1)[1])
            self.assertEqual([e['id'] for e in payload['reviewed_user_prompts']],expected)

    def test_validation_errors_distinguish_duplicates_reasons_and_evidence(self):
        request=self.request()
        base=dict(skill='ai-hero:diagnosing-bugs',reason='Useful for repeated failures.',firstStep='Diagnose a failure.',evidence=['prompt-1'])
        cases=[
            ([base,base],'duplicate recommendation'),
            ([dict(base,reason='')],'invalid recommendation reason'),
            ([dict(base,reason='x'*1201)],'invalid recommendation reason'),
            ([dict(base,evidence=[])],'between one and three supporting excerpt IDs'),
            ([dict(base,evidence=['PRIVATE invented citation'])],'outside the reviewed sample'),
        ]
        for items,message in cases:
            with self.subTest(message=message):
                self.service.generate=lambda *a:dict(summary='Summary',recommendations=items,covered=[])
                with self.assertRaisesRegex(ValueError,message) as error:
                    self.service.run(request,lambda *a:None)
                self.assertNotIn('PRIVATE',str(error.exception))

    def test_schema_states_text_limits_used_by_validation(self):
        self.service.run(self.request(),lambda *a:None)
        props=self.calls[0][2]['properties']
        fields=[props['summary']]
        for name in ('recommendations','covered'):
            fields.extend(props[name]['items']['properties'][key] for key in ('reason','firstStep'))
        for field in fields:
            self.assertEqual(field.get('minLength'),1)
            self.assertEqual(field.get('maxLength'),1200)

    def test_installed_skills_and_hallucinated_recommendations_rejected(self):
        request=self.request([dict(name='diagnosing-bugs',harnesses=['codex'])])
        with self.assertRaisesRegex(ValueError,'outside'):self.service.run(request,lambda *a:None)
        self.service.generate=lambda *a:dict(summary='Summary',covered=[],recommendations=[dict(skill=next(k for k,v in self.service.candidates([]).items() if v['name']=='tdd'),reason='Useful',firstStep='Check this implementation.',evidence=['made-up'])])
        with self.assertRaisesRegex(ValueError,'supporting'):self.service.run(self.request(),lambda *a:None)

    def test_preview_expiry_and_forged_excerpts(self):
        preview=self.service.preview(dict(target='codex',days=30))
        with self.assertRaisesRegex(ValueError,'Invalid'):
            self.service.prepare(dict(preview=preview['preview'],provider='codex',excerpts=[dict(id='unknown',text='Injected')]),[])
        self.service.previews[preview['preview']]['expires']=0
        with self.assertRaisesRegex(ValueError,'expired'):
            self.service.prepare(dict(preview=preview['preview'],provider='codex',excerpts=preview['excerpts']),[])

    def test_destination_binds_history_engine_and_install_target(self):
        self.roots['claude'].mkdir()
        (self.roots['claude']/'history.jsonl').write_text(json.dumps(dict(timestamp=time.time()*1000,display='Claude-specific design work')))
        preview=self.service.preview(dict(target='claude',sources=['codex','opencode'],days=30))
        self.assertEqual([e['source'] for e in preview['excerpts']],['claude'])
        self.assertIn('Claude-specific',preview['excerpts'][0]['text'])
        with self.assertRaisesRegex(ValueError,'match the destination'):
            self.service.prepare(dict(preview=preview['preview'],provider='codex',excerpts=preview['excerpts']),[])
        request=self.service.prepare(dict(preview=preview['preview'],provider='claude',excerpts=preview['excerpts']),[])
        result=self.service.run(request,lambda *a:None)
        self.assertEqual(self.calls[0][0],'claude')
        self.assertEqual(result['target'],'claude')
        self.assertNotIn('persistent failing test',self.calls[0][1])
        with self.assertRaises(ValueError):self.service.preview(dict(target='opencode'))

    def test_other_agents_installed_skills_remain_candidates(self):
        request=self.request([dict(name='diagnosing-bugs',harnesses=['claude'])])
        self.assertEqual(request['installed'],[])
        result=self.service.run(request,lambda *a:None)
        self.assertEqual(result['target'],'codex')
        self.assertEqual(result['recommendations'][0]['name'],'diagnosing-bugs')
        request=self.request([dict(name='diagnosing-bugs',harnesses=['codex','claude'])])
        with self.assertRaisesRegex(ValueError,'outside'):self.service.run(request,lambda *a:None)

    def test_overlap_uses_only_available_skills_and_validates_first_steps(self):
        request=self.request([dict(name='my-debugger',description='Isolate a failing test with competing hypotheses.',harnesses=['codex']),dict(name='private-claude-skill',description='CLAUDE ONLY',harnesses=['claude'])])
        self.assertEqual([s['name'] for s in request['existing']],['my-debugger'])
        self.service.generate=lambda *a:dict(summary='Your existing debugger covers this need.',recommendations=[],covered=[dict(skill='ai-hero:diagnosing-bugs',installed='my-debugger',reason='Both use minimal reproductions and competing hypotheses.',firstStep='Find a minimal reproduction of the failing test.')])
        result=self.service.run(request,lambda *a:None)
        self.assertEqual(result['covered'][0]['firstStep'],'$my-debugger Find a minimal reproduction of the failing test.')
        self.service.generate=lambda *a:dict(summary='Summary',recommendations=[],covered=[dict(skill='ai-hero:diagnosing-bugs',installed='invented',reason='Unknown',firstStep='Do this.')])
        with self.assertRaisesRegex(ValueError,'unknown'):self.service.run(request,lambda *a:None)

    def test_project_scope_includes_personal_and_matching_project_only(self):
        project=dict(id='p1',name='Portal',path='/not-sent-to-agent')
        preview=self.service.preview(dict(target='codex',project=project,scope='all'))
        installed=[dict(name='personal',harnesses=['codex']),dict(name='matching',harnesses=['codex'],project='p1'),dict(name='unrelated',harnesses=['codex'],project='p2')]
        request=self.service.prepare(dict(preview=preview['preview'],provider='codex',excerpts=preview['excerpts']),installed)
        self.assertEqual(request['installed'],['matching','personal'])
        self.service.run(request,lambda *a:None)
        self.assertNotIn('/not-sent-to-agent',self.calls[-1][1])
        self.assertIn('Portal',self.calls[-1][1])

    def test_choices_exclude_candidates_and_notes_follow_the_selected_agent(self):
        from experience import Experience
        store=Experience(self.base/'state');self.service.experience=store
        store.choose(dict(agent='codex',status='dismissed',note='Prefer another workflow'),dict(id='ai-hero:diagnosing-bugs',name='diagnosing-bugs',collection='ai-hero'),'p1')
        project=dict(id='p1',name='Portal',notes={'codex':'Backend verification','claude':'CLAUDE_PRIVATE_NOTE'})
        preview=self.service.preview(dict(target='codex',project=project,scope='all'))
        self.assertNotIn('CLAUDE_PRIVATE_NOTE',json.dumps(preview))
        request=self.service.prepare(dict(preview=preview['preview'],provider='codex',excerpts=preview['excerpts']),[])
        self.service.generate=lambda provider,prompt,schema:self.calls.append((provider,prompt,schema)) or dict(summary='No useful additions.',recommendations=[],covered=[])
        self.service.run(request,lambda *a:None)
        payload=json.loads(self.calls[-1][1].split('\n',1)[1])
        self.assertNotIn('ai-hero:diagnosing-bugs',[s['id'] for s in payload['available_skills']])
        self.assertEqual(payload['project_notes'],'Backend verification')
        self.assertEqual(payload['recommendation_preferences'][0]['note'],'Prefer another workflow')
        self.assertNotIn('CLAUDE_PRIVATE_NOTE',self.calls[-1][1])

    def test_dismissed_name_is_excluded_across_collections(self):
        request=self.request();request['choices']=[dict(skill='pstack:tdd',name='tdd',status='dismissed')]
        self.service.generate=lambda provider,prompt,schema:self.calls.append((provider,prompt,schema)) or dict(summary='No additions.',recommendations=[],covered=[])
        self.service.run(request,lambda *_:None)
        payload=json.loads(self.calls[-1][1].split('\n',1)[1])
        names=[c['name'] for c in payload['available_skills']]
        self.assertNotIn('tdd',names);self.assertEqual(len(names),len(set(names)))

    def test_review_one_recommendation_cannot_install_an_unselected_skill(self):
        manager=Manager(self.base/'skills',None,self.base/'state');self.addCleanup(manager.temporary.cleanup)
        preview=import_package(manager,bundled_collections.package(ROOT,'ai-hero'),selected_names=['diagnosing-bugs'])
        self.assertEqual([c['name'] for c in preview['candidates']],['diagnosing-bugs'])
        self.assertEqual(len(manager.drafts[preview['draft']]['paths']),1)
        with self.assertRaises(ValueError):import_package(manager,bundled_collections.package(ROOT,'ai-hero'),selected_names=['invented'])
