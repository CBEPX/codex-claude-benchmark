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

    def test_run_without_real_or_fake_flag_cannot_start_models(self):
        self.assertTrue(callable(getattr(benchmark,'main',None)), 'main missing')
        with tempfile.TemporaryDirectory() as d:
            p=subprocess.run([sys.executable,str(Path(benchmark.__file__)),'run','--output-dir',d],capture_output=True,text=True)
            self.assertEqual(p.returncode,2)
            self.assertIn('--real or --fake-bin',p.stderr)

    def test_codex_context_violation_is_an_isolation_failure(self):
        self.assertTrue(engine.isolation_errors('codex',{'context_violation':True}))


if __name__=='__main__':unittest.main()
