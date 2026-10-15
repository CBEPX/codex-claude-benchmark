"""Offline reports and replay of archived acceptance results."""
from collections import Counter, defaultdict
import html
import json
from pathlib import Path
import random
import re
import shutil
import statistics
import tempfile
import os
import engine
import archive

TASKS={'go':'Go','python':'Python','edit':'Editing','write':'Writing','search':'Text search'}


def categories(row):
    if row['status']=='invalid_protocol':return ['excluded']
    if row['passed']:return ['pass']
    tests=any('external ' in x and 'test' in x for x in row.get('errors',[]))
    primary='timeout' if row['status']=='timeout' else 'client' if row['status']!='ok' else 'tests' if tests else 'requirements'
    return [primary]+(['tests'] if tests and primary in {'timeout','client'} else [])


def summarize(rows):
    result={}
    for client in ('codex','claude'):
        all_rows=[x for x in rows if x['client']==client];eligible=[x for x in all_rows if x['status']!='invalid_protocol']
        times=[x['total_seconds'] for x in eligible if x.get('total_seconds') is not None]
        latency={}
        for key in ('first_activity_seconds','first_tool_seconds'):
            values=[x['latency'][key] for x in eligible if x.get('latency',{}).get(key) is not None]
            latency[key]={'n':len(values),'median':statistics.median(values) if values else None,'min':min(values) if values else None,'max':max(values) if values else None}
        result[client]={'attempts':len(all_rows),'eligible':len(eligible),'excluded':len(all_rows)-len(eligible),
                        'passes':sum(x['passed'] for x in eligible),'total_seconds':sum(times),'timed_attempts':len(times),
                        'client_seconds':sum(x['client_seconds'] for x in eligible if x.get('client_seconds') is not None),
                        'validation_seconds':sum(x['validation_seconds'] for x in eligible if x.get('validation_seconds') is not None),
                        'categories':dict(Counter(c for x in eligible for c in categories(x))),'latency':latency}
    return result


def failure_names(directory,task):
    names=set();p=directory/'validation/stdout.jsonl'
    if task=='go' and p.exists():
        for line in p.read_text().splitlines():
            try:e=json.loads(line)
            except ValueError:continue
            if e.get('Action')=='fail' and e.get('Test'):names.add(e['Test'])
        names={x for x in names if not any(y.startswith(x+'/') for y in names)}
    p=directory/'validation/stderr.log'
    if task=='python' and p.exists():names.update(re.findall(r'^(?:FAIL|ERROR): (.+)$',p.read_text(),re.M))
    return sorted(names)


def read_rows(root):
    return sorted([json.loads(x) for x in (Path(root)/'results.jsonl').read_text().splitlines()],key=lambda x:x['index'])


def verify_dataset(root):
    root=Path(root);bad=archive.verify_hashes(root)
    if bad:raise ValueError('Public artifact integrity failed: '+', '.join(bad))
    rows=read_rows(root);meta=json.loads((root/'dataset.json').read_text());schedule=meta['original_manifest']['schedule']
    if len(rows)!=meta['attempts'] or len({x['run_id'] for x in rows})!=len(rows):raise ValueError('Duplicate or missing result')
    original_root=engine.ROOT;engine.ROOT=root;replayed=0
    try:
        with tempfile.TemporaryDirectory(prefix='benchmark-replay-') as tmp:
            temp=Path(tmp);env=os.environ.copy();env['GOCACHE']=str(temp/'go-cache');env['GOTOOLCHAIN']='local'
            for i,row in enumerate(rows,1):
                if row['index']!=i:raise ValueError('Result index mismatch')
                if schedule and any(row[k]!=v for k,v in schedule[i-1].items()):raise ValueError('Schedule mismatch')
                if row['status']=='invalid_protocol':continue
                if row['passed']!=(row['status']=='ok' and not row.get('errors')):raise ValueError('PASS inconsistent with recorded status')
                work=temp/row['run_id']/'work';shutil.copytree(root/'fixtures'/row['task'],work)
                artifact='records.go' if row['task']=='go' else 'aggregate.py' if row['task']=='python' else 'result.json' if row['task']=='search' else 'result.md'
                source=root/'runs'/row['run_id']/'work'/artifact
                if not source.exists():raise ValueError('Missing model artifact: '+row['run_id'])
                shutil.copy2(source,work/artifact);logs=temp/row['run_id']/'check'
                checked=engine.validate_run(row['task'],work,logs,env)
                expected_tests=any('external ' in x and 'test' in x for x in row.get('errors',[]))
                expected_other=[x for x in row.get('errors',[]) if not x.startswith(('client error:','expected exact main','complete Claude','clean isolation'))]
                expected_bad=expected_tests if row['task'] in {'go','python'} else bool(expected_other)
                if bool(checked['errors'])!=expected_bad:raise ValueError('Acceptance outcome changed: '+row['run_id']+' '+str(checked['errors']))
                if row['task']=='go' and failure_names(logs,'go')!=failure_names(root/'runs'/row['run_id'],'go'):
                    raise ValueError('Failing Go test names changed: '+row['run_id'])
                replayed+=1
    finally:engine.ROOT=original_root
    return {'dataset':meta['dataset_id'],'attempts':len(rows),'replayed':replayed,'categories':dict(Counter(c for row in rows for c in categories(row))),'clients':summarize(rows)}


def table(values):
    escaped=[[str(x).replace('|','\\|').replace('\n',' ') for x in row] for row in values]
    return '\n'.join('| '+' | '.join(row)+' |' for row in [escaped[0],['---']*len(escaped[0]),*escaped[1:]])


def render(datasets,destination):
    destination=Path(destination);destination.mkdir(parents=True,exist_ok=True)
    md=['# Codex CLI and Claude Code benchmark','',
        'Times include CLI startup, model and tool work, cleanup, event parsing, and external acceptance. Medians use PASS attempts only. Ratios require three PASS attempts from both clients. Text PASS checks formal requirements. Human style acceptance remains open.','']
    pages=[];summary={};pairs=0
    for root in datasets:
        root=Path(root);meta=json.loads((root/'dataset.json').read_text());name=meta['dataset_id'];rows=read_rows(root);summary[name]=summarize(rows)
        md+=['## '+name,'',f"Recorded attempts: {len(rows)}. Excluded preparation incidents: {sum(x['status']=='invalid_protocol' for x in rows)}.",'']
        totals=[['Client','PASS / eligible','Total attempted seconds','CLI seconds','External check seconds','First tool median seconds (n)']]
        for client,stats in summary[name].items():
            l=stats['latency']['first_tool_seconds'];lt=f"{l['median']:.2f} ({l['n']})" if l['n'] else 'unavailable (0)'
            totals.append([client,f"{stats['passes']}/{stats['eligible']}",f"{stats['total_seconds']:.2f}",f"{stats['client_seconds']:.2f}",f"{stats['validation_seconds']:.2f}",lt])
        md +=[table(totals),'','Totals include failed and timed-out eligible attempts. Preparation incidents are reported separately and are not counted as model failures.','']
        values=[['Mode / task','Codex: PASS; median [min-max] s','Codex failures','Claude: PASS; median [min-max] s','Claude failures','Faster with 3/3 PASS']]
        for mode in sorted({x['mode'] for x in rows}):
            for task,title in TASKS.items():
                medians=[];complete=[];cells=[]
                for client in ('codex','claude'):
                    group=[x for x in rows if (x['mode'],x['task'],x['client'])==(mode,task,client)]
                    eligible=[x for x in group if x['status']!='invalid_protocol'];times=[x['total_seconds'] for x in eligible if x['passed']]
                    median=statistics.median(times) if times else None;medians.append(median);complete.append(len(group)==3 and len(times)==3)
                    timing=f'{median:.2f} [{min(times):.2f}-{max(times):.2f}]' if times else 'unavailable'
                    failures=Counter(c for x in group if not x['passed'] for c in categories(x))
                    cells +=[f'{len(times)}/{len(eligible)}; {timing}',', '.join(f'{k}: {v}' for k,v in failures.items()) or '-']
                winner='-'
                if all(complete):winner=('Codex' if medians[0]<medians[1] else 'Claude')+f' x{max(medians)/min(medians):.2f}'
                values.append([mode+' / '+title,*cells,winner])
        md +=[table(values),'','### Failed and excluded attempts','']
        failures=[['Run','Outcome','Failed checks / recorded reason','Seconds']]
        for row in rows:
            if row['passed']:continue
            detail='; '.join(failure_names(root/'runs'/row['run_id'],row['task'])) or '; '.join(row.get('errors',[]))
            seconds=f"{row['total_seconds']:.2f}" if row.get('total_seconds') is not None else 'not recorded'
            failures.append([row['run_id'],' + '.join(categories(row)),detail,seconds])
        md +=[table(failures),'']
        pages.append('<h2>'+html.escape(name)+'</h2>')
        for mode in sorted({x['mode'] for x in rows}):
            for task in ('edit','write'):
                for rep in (1,2,3):
                    pair=[x for x in rows if (x['mode'],x['task'],x['rep'])==(mode,task,rep)]
                    if len(pair)!=2:continue
                    random.Random(f'{name}-{mode}-{task}-{rep}').shuffle(pair);pairs+=1
                    pages.append(f'<h3>{mode} / {task} / repetition {rep}</h3><div class="pair">')
                    for letter,row in zip('AB',pair):
                        p=root/'runs'/row['run_id']/'work/result.md';text=p.read_text() if p.exists() else '(artifact missing)'
                        pages.append('<article><h4>'+letter+'</h4><pre>'+html.escape(text)+'</pre></article>')
                    pages.append('</div><details><summary>Reveal clients and times</summary><p>'+html.escape('; '.join(f"{a}: {x['client']}, {x['total_seconds']:.2f} s, PASS={x['passed']}" for a,x in zip('AB',pair)))+'</p></details>')
    md+=['## Limits','',
         'Original and clean series have different advisor and extension policies. The clean series uses high effort for both clients. Original native Claude uses xhigh. Separate system prompts and tools remain. Effort names are not equivalent across providers. Three repetitions do not establish statistical significance. Server cache and background machine load are not isolated. Codex model identity is requested, not independently verified backend identity. First-event timing is not TTFT. Missing measurements are unavailable, not zero. Generation TPS is unavailable.','']
    text='\n'.join(md);(destination/'RESULTS.md').write_text(text)
    style='<style>body{font:16px system-ui;max-width:1500px;margin:32px auto;padding:0 20px}.pair{display:grid;grid-template-columns:1fr 1fr;gap:20px}article{border:1px solid #bbb;padding:15px}pre{white-space:pre-wrap;overflow-wrap:anywhere}details{margin:16px 0}@media(max-width:800px){.pair{grid-template-columns:1fr}}</style>'
    page='<!doctype html><html lang="en"><meta charset="utf-8"><title>Codex / Claude benchmark</title>'+style+'<h1>Results</h1><pre>'+html.escape(text)+'</pre><h1>Blind text comparisons</h1>'+''.join(pages)+'</html>'
    (destination/'comparison.html').write_text(page)
    (destination/'summary.json').write_text(json.dumps({'datasets':summary,'blind_pairs':pairs},indent=2)+'\n')
    return {'datasets':len(datasets),'blind_pairs':pairs}
