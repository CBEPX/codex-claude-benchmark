import json
import os
from pathlib import Path
import signal
import subprocess
import sys
import tempfile
import unittest
import engine
import benchmark


class EngineTests(unittest.TestCase):
    def test_event_receipt_timing_covers_startup_and_stdin_without_deadlock(self):
        self.assertTrue(callable(getattr(engine,'run_process',None)), 'run_process missing')
        with tempfile.TemporaryDirectory() as d:
            root=Path(d)
            source='import sys,time,json; p=sys.stdin.read(); time.sleep(.06); print(json.dumps({"type":"item.completed","item":{"type":"agent_message","text":p}}),flush=True); time.sleep(.06); print(json.dumps({"type":"turn.completed","usage":{"output_tokens":1}}),flush=True)'
            r=engine.run_process([sys.executable,'-c',source],root,root,3,prompt='INPUT_OK',capture_events=True)
            self.assertEqual(r['status'],'ok')
            lines=[json.loads(x) for x in (root/'events-timing.jsonl').read_text().splitlines()]
            self.assertEqual(len(lines),2)
            self.assertGreaterEqual(lines[0]['elapsed_seconds'],.06)
            self.assertGreater(lines[1]['elapsed_seconds'],lines[0]['elapsed_seconds'])
            self.assertTrue(lines[0]['activity']);self.assertEqual(lines[0]['source_line'],1)
            self.assertIn('INPUT_OK',(root/'stdout.jsonl').read_text())

    def test_timeout_stops_a_detached_child(self):
        self.assertTrue(callable(getattr(engine,'run_process',None)), 'run_process missing')
        with tempfile.TemporaryDirectory() as d:
            root=Path(d)
            code='import subprocess,sys,time; p=subprocess.Popen([sys.executable,"-c","import time;time.sleep(30)"],start_new_session=True);open("child","w").write(str(p.pid));time.sleep(30)'
            r=engine.run_process([sys.executable,'-c',code],root,root,.5)
            pid=int((root/'child').read_text())
            try:
                state=subprocess.run(['ps','-o','stat=','-p',str(pid)],capture_output=True,text=True)
                self.assertTrue(state.returncode!=0 or state.stdout.strip().startswith('Z'))
                self.assertEqual(r['status'],'timeout');self.assertTrue(r['cleanup_verified'])
            finally:
                try:os.kill(pid,signal.SIGKILL)
                except ProcessLookupError:pass

    def test_profile_does_not_change_source_config_or_copy_credentials(self):
        self.assertTrue(callable(getattr(benchmark,'make_profile',None)), 'make_profile missing')
        with tempfile.TemporaryDirectory() as d:
            root=Path(d);source=root/'source';source.mkdir();dest=root/'runtime'
            (source/'config.toml').write_text('model="caller-model"\n')
            (source/'auth.json').write_text('SYNTHETIC_AUTH_FIXTURE')
            benchmark.make_profile(dest,source)
            self.assertEqual((source/'config.toml').read_text(),'model="caller-model"\n')
            self.assertTrue((dest/'auth.json').is_symlink())
            self.assertEqual((dest/'auth.json').resolve(),(source/'auth.json').resolve())
            self.assertNotIn('SYNTHETIC_AUTH_FIXTURE',(dest/'config.toml').read_text())

    def test_profile_disables_host_user_skills_by_exact_path(self):
        from unittest.mock import patch
        import tomllib
        with tempfile.TemporaryDirectory() as d:
            home=Path(d);skill=home/'.agents/skills/custom/SKILL.md';skill.parent.mkdir(parents=True);skill.write_text('synthetic skill')
            with patch.object(Path,'home',return_value=home):
                benchmark.make_profile(home/'runtime',home/'source')
            disabled=tomllib.loads((home/'runtime/config.toml').read_text())['skills']['config']
            self.assertIn({'path':str(skill.resolve()),'enabled':False},disabled)

    def test_run_without_real_or_fake_flag_cannot_start_models(self):
        self.assertTrue(callable(getattr(benchmark,'main',None)), 'main missing')
        with tempfile.TemporaryDirectory() as d:
            p=subprocess.run([sys.executable,str(Path(benchmark.__file__)),'run','--output-dir',d],capture_output=True,text=True)
            self.assertEqual(p.returncode,2)
            self.assertIn('--real or --fake-bin',p.stderr)

    def test_unverified_cleanup_stops_both_clients(self):
        for client in ('codex','claude'):
            for state in ({'status':'cleanup_error','cleanup_verified':False}, {'status':'ok','cleanup_verified':False}):
                with self.subTest(client=client,state=state):
                    self.assertTrue(engine.isolation_errors(client,state))

    def test_missing_code_artifact_is_a_recorded_acceptance_failure(self):
        with tempfile.TemporaryDirectory() as d:
            root=Path(d);work=root/'work';work.mkdir()
            for task in ('go','python'):
                with self.subTest(task=task):
                    result=engine.validate_run(task,work,root/task,os.environ.copy())
                    self.assertTrue(any('missing model artifact' in e for e in result['errors']))
                    self.assertGreaterEqual(result['validation_seconds'],0)

    def test_external_acceptance_cleanup_failure_blocks_series(self):
        from unittest.mock import patch
        with tempfile.TemporaryDirectory() as d:
            root=Path(d);work=root/'work'
            import shutil
            shutil.copytree(engine.ROOT/'fixtures/python',work)
            def incomplete(command,cwd,logs,*a,**kw):
                logs.mkdir(parents=True);(logs/'stdout.jsonl').write_text('');(logs/'stderr.log').write_text('')
                return {'status':'cleanup_error','cleanup_verified':False}
            with patch.object(engine,'run_process',side_effect=incomplete):
                result=engine.validate_run('python',work,root/'logs',os.environ.copy())
            self.assertTrue(engine.isolation_errors('codex',result))

    def test_codex_context_violation_is_an_isolation_failure(self):
        self.assertTrue(engine.isolation_errors('codex',{'context_violation':True}))


if __name__=='__main__':unittest.main()
