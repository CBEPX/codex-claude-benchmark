import json
from pathlib import Path
import subprocess
import sys
import tempfile
import unittest

ROOT=Path(__file__).resolve().parents[1]


def fake_clients(directory):
    directory.mkdir()
    source='#!'+sys.executable+'''\nimport json,os,pathlib,shutil,sys
client=pathlib.Path(sys.argv[0]).name
if '--version' in sys.argv:
 print('codex-cli 0.162.1' if client=='codex' else '2.1.300 (Claude Code)');sys.exit()
prompt=sys.stdin.read();work=pathlib.Path.cwd()
probe='CLEAN_READY' in prompt
if client=='codex':
 assert '--no-daemon' in sys.argv and '--json' in sys.argv
 assert pathlib.Path(sys.argv[sys.argv.index('--add-dir')+1]).is_dir()
 print(json.dumps({'type':'thread.started','thread_id':'fake-thread'}))
 print(json.dumps({'type':'item.completed','item':{'type':'agent_message','text':'CLEAN_READY' if probe else 'Starting.'}}))
else:
 assert '--safe-mode' in sys.argv and '--strict-mcp-config' in sys.argv and '--disable-slash-commands' in sys.argv
 assert os.environ.get('CLAUDE_CODE_DISABLE_ADVISOR_TOOL')=='1'
 print(json.dumps({'type':'system','subtype':'init','model':'claude-opus-5-5','plugins':[],'mcp_servers':[],'tools':['Bash','Read','Write','Edit','Glob','Grep']}))
 print(json.dumps({'type':'assistant','message':{'model':'claude-opus-5-5','content':[{'type':'text','text':'CLEAN_READY' if probe else 'Starting.'}]}}))
if not probe:
 o=pathlib.Path(os.environ['BENCHMARK_FAKE_ORACLE'])
 if (work/'records.go').exists():shutil.copy2(o/'records.go',work/'records.go')
 elif (work/'aggregate.py').exists():shutil.copy2(o/'aggregate.py',work/'aggregate.py')
 elif (work/'source.md').exists():shutil.copy2(o/'edit.md',work/'result.md')
 elif (work/'facts.md').exists():shutil.copy2(o/'write.md',work/'result.md')
 else:(work/'result.json').write_text(json.dumps(json.loads((o/'search.json').read_text())['answers']))
if client=='codex':
 if '-o' in sys.argv:pathlib.Path(sys.argv[sys.argv.index('-o')+1]).write_text('CLEAN_READY' if probe else 'Done.')
 print(json.dumps({'type':'turn.completed','usage':{'output_tokens':42}}))
else:print(json.dumps({'type':'result','subtype':'success','is_error':False,'result':'CLEAN_READY' if probe else 'Done.','usage':{'output_tokens':42},'modelUsage':{'claude-opus-5-5':{}}}))
'''
    for client in ('codex','claude'):
        p=directory/client;p.write_text(source);p.chmod(0o700)


class RunnerTests(unittest.TestCase):
    def test_explicit_fake_mode_completes_30_unique_validated_runs(self):
        with tempfile.TemporaryDirectory() as d:
            root=Path(d);fake=root/'fake';fake_clients(fake);out=root/'run'
            p=subprocess.run([sys.executable,str(ROOT/'benchmark.py'),'run','--fake-bin',str(fake),'--output-dir',str(out)],capture_output=True,text=True,timeout=90)
            self.assertEqual(p.returncode,0,p.stdout+'\n'+p.stderr)
            rows=[json.loads(x) for x in (out/'results.jsonl').read_text().splitlines()]
            self.assertEqual(len(rows),30);self.assertEqual(len({x['run_id'] for x in rows}),30)
            self.assertTrue(all(x['passed'] for x in rows))
            self.assertTrue(all(x['latency']['basis']=='monotonic_received_event' for x in rows))
            self.assertTrue(json.loads((out/'preflight.json').read_text())['fake'])
            self.assertEqual(json.loads((out/'manifest.json').read_text())['contract_version'],'tasks-v2')
            self.assertFalse((out/'profiles/codex-controlled/auth.json').exists())

    def test_resume_checks_prior_isolation_failure_before_probe_dispatch(self):
        import benchmark
        from unittest.mock import patch
        with tempfile.TemporaryDirectory() as d:
            root=Path(d);fake=root/'fake';fake_clients(fake);out=root/'run';out.mkdir();(out/'profiles/codex-controlled').mkdir(parents=True)
            bins={c:str((fake/c).resolve()) for c in ('codex','claude')}
            config={'codex_model':'gpt-6.1-sol','claude_model':'claude-opus-5-5','effort':'high','fake':True,'executables':bins,'versions':{'codex':'codex-cli 0.162.1','claude':'2.1.300 (Claude Code)'},'timeout_seconds':300}
            (out/'manifest.json').write_text(json.dumps({'configuration':config,'files':{},'runner_source_sha256':{},'schedule':[]}))
            (out/'results.jsonl').write_text(json.dumps({'client':'claude','status':'ok','isolation_evidence_complete':True,'advisor_calls':1})+'\n')
            with patch.object(benchmark,'qualify',side_effect=ValueError('would launch a probe')):
                with self.assertRaisesRegex(ValueError,'Prior isolation'):
                    benchmark.main(['run','--fake-bin',str(fake),'--output-dir',str(out),'--resume'])

    def test_partial_codex_json_preserves_attempt_and_stops_resume(self):
        import benchmark
        from unittest.mock import patch
        with tempfile.TemporaryDirectory() as d:
            root=Path(d);fake=root/'fake';fake_clients(fake);out=root/'run'
            p=fake/'codex';p.write_text(p.read_text()+"\nif not probe:print('{partial')\n")
            with patch.object(benchmark,'qualify'):
                with self.assertRaisesRegex(ValueError,'Isolation failure'):
                    benchmark.main(['run','--fake-bin',str(fake),'--output-dir',str(out)])
            rows=[json.loads(x) for x in (out/'results.jsonl').read_text().splitlines()]
            self.assertEqual(len(rows),1);self.assertFalse(rows[0]['passed'])
            self.assertTrue(rows[0]['postprocessing_failed'])
            self.assertTrue((out/'runs'/rows[0]['run_id']/'result.json').is_file())
            with patch.object(benchmark,'qualify',side_effect=AssertionError('must not dispatch')):
                with self.assertRaisesRegex(ValueError,'Prior isolation'):
                    benchmark.main(['run','--fake-bin',str(fake),'--output-dir',str(out),'--resume'])

    def test_cleanup_failure_is_persisted_before_next_dispatch(self):
        import benchmark,engine
        from unittest.mock import patch
        with tempfile.TemporaryDirectory() as d:
            root=Path(d);fake=root/'fake';fake_clients(fake);out=root/'run';original=engine.run_process
            def unverified(*a,**kw):
                result=original(*a,**kw);result.update(status='cleanup_error',cleanup_verified=False);return result
            with patch.object(benchmark,'qualify'),patch.object(engine,'run_process',side_effect=unverified) as calls:
                with self.assertRaisesRegex(ValueError,'Isolation failure'):
                    benchmark.main(['run','--fake-bin',str(fake),'--output-dir',str(out)])
            self.assertEqual(calls.call_count,1)
            rows=[json.loads(x) for x in (out/'results.jsonl').read_text().splitlines()]
            self.assertEqual(len(rows),1);self.assertFalse(rows[0]['passed'])

    def test_partial_profile_setup_failure_removes_owned_auth_link(self):
        import benchmark
        from unittest.mock import patch
        with tempfile.TemporaryDirectory() as d:
            root=Path(d);fake=root/'fake';fake_clients(fake);out=root/'run';source=root/'source';source.mkdir();(source/'auth.json').write_text('SYNTHETIC_AUTH_FIXTURE')
            original=benchmark.make_profile
            def fail_after_link(destination,ignored_source):
                original(destination,source)
                raise ValueError('profile setup interrupted')
            with patch.object(benchmark,'make_profile',side_effect=fail_after_link):
                with self.assertRaisesRegex(ValueError,'profile setup interrupted'):
                    benchmark.main(['run','--fake-bin',str(fake),'--output-dir',str(out)])
            self.assertFalse((out/'profiles/codex-controlled/auth.json').is_symlink())


if __name__=='__main__':unittest.main()
