import json
from pathlib import Path
import tempfile
import unittest
import archive


class ArchiveTests(unittest.TestCase):
    def test_export_drops_account_metadata_but_keeps_model_and_time(self):
        self.assertTrue(callable(getattr(archive, 'public_event', None)), 'public_event missing')
        event = {'type':'assistant','timestamp':'2026-10-15T12:00:00Z','session_id':'11111111-2222-4333-8444-555555555555',
                 'account_id':'private-account','request_id':'private-request','apiKey':'DO_NOT_EXPORT',
                 'message':{'model':'claude-opus-5-5','content':[{'type':'text','text':'Finished.'}], 'usage':{'output_tokens':7}}}
        result = archive.public_event(event)
        raw = json.dumps(result)
        self.assertNotIn('private-account', raw)
        self.assertNotIn('private-request', raw)
        self.assertNotIn('DO_NOT_EXPORT', raw)
        self.assertEqual(result['timestamp'], '2026-10-15T12:00:00Z')
        self.assertEqual(result['message']['model'], 'claude-opus-5-5')
        self.assertEqual(result['message']['usage']['output_tokens'], 7)

    def test_redaction_removes_home_paths_and_private_gitlab_urls(self):
        self.assertTrue(callable(getattr(archive, 'sanitize_text', None)), 'sanitize_text missing')
        text = 'Read /Users/test-person/work/main.py and https://gitlab.internal.example/group/repo/-/issues/9'
        result = archive.sanitize_text(text)
        self.assertNotIn('/Users/test-person', result)
        self.assertNotIn('gitlab.internal.example', result)
        self.assertIn('main.py', result)

    def test_integrity_verification_rejects_changed_public_artifact(self):
        self.assertTrue(callable(getattr(archive, 'seal', None)), 'seal missing')
        self.assertTrue(callable(getattr(archive, 'verify_hashes', None)), 'verify_hashes missing')
        with tempfile.TemporaryDirectory() as d:
            root=Path(d);p=root/'result.txt';p.write_text('original')
            archive.seal(root)
            self.assertEqual(archive.verify_hashes(root), [])
            p.write_text('modified')
            self.assertEqual(archive.verify_hashes(root), ['result.txt'])

    def test_export_uses_allowlist_and_preserves_failed_attempt(self):
        self.assertTrue(callable(getattr(archive, 'export_series', None)), 'export_series missing')
        with tempfile.TemporaryDirectory() as d:
            src=Path(d)/'private';src.mkdir();out=Path(d)/'public'
            (src/'manifest.json').write_text(json.dumps({'files':{},'schedule':[], 'models':{},'cli_versions':{},'timeout_seconds':300}))
            row={'run_id':'01-go-claude','index':1,'client':'claude','task':'go','mode':'controlled','rep':1,
                 'passed':False,'status':'ok','total_seconds':9.5,'errors':['external acceptance tests: error']}
            (src/'results.jsonl').write_text(json.dumps(row)+'\n')
            (src/'auth.json').write_text('DO_NOT_EXPORT_CREDENTIAL')
            logs=src/'runs'/row['run_id'];(logs/'work').mkdir(parents=True)
            (logs/'work/records.go').write_text('package records\n')
            (logs/'work/AGENTS.md').write_text('DO_NOT_EXPORT_INSTRUCTIONS')
            (logs/'stdout.jsonl').write_text(json.dumps({'type':'system','subtype':'init','model':'claude-opus-5-5','account_id':'DO_NOT_EXPORT_ACCOUNT'})+'\n')
            archive.export_series(src,out,'example')
            raw=''.join(p.read_text() for p in out.rglob('*') if p.is_file())
            self.assertNotIn('DO_NOT_EXPORT',raw)
            got=json.loads((out/'results.jsonl').read_text())
            self.assertFalse(got['passed']);self.assertEqual(got['total_seconds'],9.5)
            self.assertTrue((out/'runs/01-go-claude/work/records.go').exists())

    def test_historical_latency_keeps_timestamps_needed_to_recompute_it(self):
        with tempfile.TemporaryDirectory() as d:
            root=Path(d);logs=root/'runs/r1';logs.mkdir(parents=True)
            (logs/'stdout.jsonl').write_text(json.dumps({'type':'assistant','timestamp':'2026-10-15T12:00:03Z','message':{'content':[{'type':'tool_use'}]}})+'\n')
            row={'run_id':'r1','client':'claude','started_at':'2026-10-15T15:00:00+03:00'}
            result=archive.first_events(row,root)
            self.assertEqual(result['first_tool_seconds'],3)
            self.assertEqual(result.get('first_tool_at'),'2026-10-15T12:00:03Z')

    def test_historical_latency_excludes_thinking_only_events(self):
        with tempfile.TemporaryDirectory() as d:
            root=Path(d);logs=root/'runs/r1';logs.mkdir(parents=True)
            events=[{'type':'assistant','timestamp':'2026-10-15T12:00:01Z','message':{'content':[{'type':'thinking','thinking':'private'}]}},
                    {'type':'assistant','timestamp':'2026-10-15T12:00:03Z','message':{'content':[{'type':'text','text':'Ready'}]}},
                    {'type':'assistant','timestamp':'2026-10-15T12:00:04Z','message':{'content':[{'type':'tool_use'}]}}]
            (logs/'stdout.jsonl').write_text(''.join(json.dumps(e)+'\n' for e in events))
            result=archive.first_events({'run_id':'r1','client':'claude','started_at':'2026-10-15T12:00:00Z'},root)
            self.assertEqual(result['first_activity_seconds'],3)
            self.assertEqual(result['first_tool_seconds'],4)

    def test_excluded_legacy_plain_validation_log_is_preserved_as_text(self):
        with tempfile.TemporaryDirectory() as d:
            src=Path(d)/'source';src.mkdir();out=Path(d)/'public'
            (src/'manifest.json').write_text(json.dumps({'files':{},'schedule':[]}))
            (src/'results.jsonl').write_text(json.dumps({'run_id':'r1','client':'codex','task':'go','status':'invalid_protocol','passed':False})+'\n')
            p=src/'runs/r1/validation';p.mkdir(parents=True);(p/'stdout.jsonl').write_text('--- FAIL: TestAcceptance\n')
            archive.export_series(src,out,'legacy')
            target=out/'runs/r1/validation/stdout.txt'
            self.assertTrue(target.is_file());self.assertEqual(target.read_text(),'--- FAIL: TestAcceptance\n')


if __name__=='__main__':unittest.main()
