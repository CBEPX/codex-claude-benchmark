"""Post-hoc sensitivity analysis; never replaces historical scores or timings."""
import json
import os
from pathlib import Path
import shutil
import subprocess
import tempfile

ROOT=Path(__file__).resolve().parent

def analyze():
    dataset=ROOT/'datasets/2026-10-15-clean'
    original=(dataset/'oracle/acceptance_test.go').read_text()
    omitted=' {"zero-limit","",0,nil,true},\n'
    if original.count(omitted)!=1:raise ValueError('Historical zero-limit case changed')
    results=[]
    with tempfile.TemporaryDirectory() as d:
        work=Path(d)
        for name in ('go.mod','records_test.go'):shutil.copy2(dataset/'fixtures/go'/name,work/name)
        (work/'acceptance_test.go').write_text(original.replace(omitted,''))
        for row in map(json.loads,(dataset/'results.jsonl').read_text().splitlines()):
            if row['task']!='go':continue
            shutil.copy2(dataset/'runs'/row['run_id']/'work/records.go',work/'records.go')
            p=subprocess.run(['go','test','-json','-count=1','./...'],cwd=work,capture_output=True,text=True,timeout=45,env={**os.environ,'GOTOOLCHAIN':'local'})
            events=[json.loads(x) for x in p.stdout.splitlines()]
            failed=sorted(e['Test'] for e in events if e.get('Action')=='fail' and e.get('Test'))
            results.append({'run_id':row['run_id'],'client':row['client'],'passed_without_zero_limit':p.returncode==0,'failed_tests':failed})
    return {'analysis':'post-hoc omission of zero-limit only','new_model_requests':0,'historical_scores_changed':False,'timings_recomputed':False,'results':results}

if __name__=='__main__':print(json.dumps(analyze(),indent=2))
