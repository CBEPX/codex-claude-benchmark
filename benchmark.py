"""Portable benchmark: offline evidence verification and explicit model execution."""
import argparse
import json
import os
from pathlib import Path
import shutil
import sys
import hashlib
import re
import random
import subprocess
import time
import engine
import archive
import reporting

ROOT=Path(__file__).resolve().parent


def make_profile(destination,source_home):
    destination=Path(destination);source_home=Path(source_home)
    destination.mkdir(parents=True,exist_ok=True)
    config='''service_tier = "default"
project_doc_max_bytes = 0
[features]
hooks = false
memories = false
apps = false
plugins = false
multi_agent = false
skip_host_skill_discovery = true
'''
    names={'imagegen','openai-docs','skill-creator','skill-installer'}
    system=source_home/'skills/.system'
    if system.exists():names|={p.parent.name for p in system.glob('*/SKILL.md')}
    for name in sorted(names):
        config+='\n[[skills.config]]\npath = '+json.dumps(str(destination/'skills/.system'/name/'SKILL.md'))+'\nenabled = false\n'
    (destination/'config.toml').write_text(config)
    auth=source_home/'auth.json'
    if auth.is_file():(destination/'auth.json').symlink_to(auth.resolve())
    return destination



def schedule():
    blocks=[(task,rep) for task in ('go','python','edit','write','search') for rep in (1,2,3)]
    random.Random(20261015).shuffle(blocks)
    return [{'task':t,'rep':r,'mode':'controlled','client':c} for i,(t,r) in enumerate(blocks) for c in (('codex','claude') if i%2==0 else ('claude','codex'))]


def executables(args):
    if args.fake_bin:
        directory=args.fake_bin.resolve();result={c:str(directory/c) for c in ('codex','claude')}
        if any(not Path(p).is_file() or Path(p).resolve().parent!=directory for p in result.values()):raise ValueError('Fake executables must be real files inside --fake-bin')
        return result
    result={}
    for client in ('codex','claude'):
        value=getattr(args,client+'_bin') or shutil.which(client)
        if not value or not Path(value).is_file():raise ValueError(client+' executable not found')
        result[client]=str(Path(value).resolve())
    return result


def client_env(client,root,fake=False):
    env=os.environ.copy()
    for name in ('CODEX_THREAD_ID','CLAUDECODE','CLAUDE_CODE_ENTRYPOINT'):env.pop(name,None)
    env['GOCACHE']=str(root/'cache/go');env['GOTOOLCHAIN']='local'
    if client=='codex':env['CODEX_HOME']=str(root/'profiles/codex-controlled')
    else:env['CLAUDE_CODE_DISABLE_ADVISOR_TOOL']='1'
    if fake:env['BENCHMARK_FAKE_ORACLE']=str(ROOT/'oracle')
    else:env.pop('BENCHMARK_FAKE_ORACLE',None)
    return env


def command(client,root,logs,bins,args):
    if client=='codex':return [bins[client],'--no-daemon','exec','--json','--skip-git-repo-check','-m',args.codex_model,'-c','model_reasoning_effort='+json.dumps(args.effort),'-c','approval_policy="never"','-s','workspace-write','--add-dir',str(root/'cache'),'-o',str(logs/'final.txt'),'-']
    return [bins[client],'--print','--model',args.claude_model,'--effort',args.effort,'--verbose','--output-format','stream-json','--include-hook-events','--permission-mode','dontAsk','--permission-prompts','none','--tools','Bash,Read,Write,Edit,Glob,Grep','--allowedTools','Bash,Read,Write,Edit,Glob,Grep','--safe-mode','--strict-mcp-config','--mcp-config','{"mcpServers":{}}','--setting-sources','','--settings',str(root/'profiles/claude-clean.json'),'--disable-slash-commands']


def read_events(path):
    return [json.loads(x) for x in Path(path).read_text().splitlines()]


def check_codex_context(root,stdout):
    tid=next(e['thread_id'] for e in read_events(stdout) if e.get('type')=='thread.started')
    paths=list((root/'profiles/codex-controlled/sessions').rglob('*'+tid+'.jsonl'))
    if len(paths)!=1:raise ValueError('Current Codex session context missing or ambiguous')
    events=read_events(paths[0])
    if not any(e.get('type')=='session_meta' and e.get('payload',{}).get('id')==tid for e in events):raise ValueError('Codex session identity mismatch')
    contexts=[e for e in events if e.get('type')=='session_meta' or (e.get('type')=='response_item' and e.get('payload',{}).get('role') in {'user','developer'})]
    raw=json.dumps(contexts,ensure_ascii=False)
    markers=[x for x in ('# AGENTS.md instructions','Global Codex Instructions','PONYTAIL MODE ACTIVE','=== REMEMBER ===','You have superpowers') if x in raw]
    if re.search(r'### Available skills(?:\\n)+- ',raw):markers.append('user skill catalog')
    if markers:raise ValueError('Codex custom context found: '+str(markers))
    return {'custom_instruction_markers':[],'context_sha256':hashlib.sha256(raw.encode()).hexdigest()}


def check_claude_context(stdout):
    init=next(e for e in read_events(stdout) if e.get('subtype')=='init')
    auto=init.get('memory_paths',{}).get('auto')
    directory=Path(auto).parent if auto else Path.home()/'.claude/projects'/re.sub('[^a-zA-Z0-9]','-',init['cwd'])
    entries=read_events(directory/(init['session_id']+'.jsonl'))
    attachments=[e['attachment'] for e in entries if e.get('attachment',{}).get('type')=='advisor_tool']
    if any(e.get('available') for e in attachments):raise ValueError('Claude advisor is available')
    return {'advisor_available_in_transcript':False,'advisor_disable_env':'1'}


def latency(logs):
    events=read_events(logs/'events-timing.jsonl')
    first=next((e for e in events if e['activity']),None);tool=next((e for e in events if e['tool']),None)
    return {'basis':'monotonic_received_event','first_activity_seconds':first['elapsed_seconds'] if first else None,'first_tool_seconds':tool['elapsed_seconds'] if tool else None,'coverage':'available' if first and tool else 'partial'}


def check_frozen(root,manifest):
    bad=[name for name,h in manifest['files'].items() if not (root/name).is_file() or engine.input_digest(root/name)!=h]
    bad +=[name for name,h in manifest['runner_source_sha256'].items() if archive.digest(ROOT/name)!=h]
    if bad:raise ValueError('Frozen inputs changed: '+', '.join(bad))


def qualify(root,args,bins):
    result={'fake':bool(args.fake_bin),'scored':False,'customization_free':True,'advisor_disabled':True,'probes':{}}
    prompt='Authorized isolated benchmark probe. Do not use tools, delegation, skills or network search. Reply exactly CLEAN_READY and finish.'
    for client in ('claude','codex'):
        logs=root/'preflight'/client;checkpoint=logs/'result.json'
        if checkpoint.exists():
            if not args.resume:raise ValueError('Existing probe needs --resume; it will not be repeated')
            r=json.loads(checkpoint.read_text())
        elif logs.exists():raise ValueError('Unrecorded probe exists; audit before continuing')
        else:
            work=logs/'work';work.mkdir(parents=True);subprocess.run(['git','init','--quiet'],cwd=work,check=True)
            r=engine.run_process(command(client,root,logs,bins,args),work,logs,90,env=client_env(client,root,bool(args.fake_bin)),prompt=prompt,capture_events=True)
            checkpoint.write_text(json.dumps(r,indent=2))
        r.update(engine.event_summary(client,logs/'stdout.jsonl'))
        if r['status']!='ok' or not r['cleanup_verified'] or engine.model_errors(client,r):raise ValueError('Isolation probe failed: '+client+' '+str(engine.model_errors(client,r)))
        if not args.fake_bin:
            r.update(check_codex_context(root,logs/'stdout.jsonl') if client=='codex' else check_claude_context(logs/'stdout.jsonl'))
        if client=='codex':answer=(logs/'final.txt').read_text().strip()
        else:answer=next(e.get('result','') for e in reversed(read_events(logs/'stdout.jsonl')) if e.get('type')=='result').strip()
        if answer!='CLEAN_READY':raise ValueError('Probe did not return exact CLEAN_READY')
        checkpoint.write_text(json.dumps(r,indent=2));result['probes'][client]={'status':r['status'],'client_seconds':r['client_seconds'],'advisor_calls':r['advisor_calls'],'hook_events':r['hook_events']}
        print(json.dumps({'probe':client,'status':'PASS','fake':bool(args.fake_bin)}),flush=True)
    (root/'preflight.json').write_text(json.dumps(result,indent=2))
    return result


def run(args):
    root=args.output_dir.resolve()
    if root.exists() and not args.resume:raise ValueError('Output directory exists; use a new path or explicit --resume')
    root.mkdir(parents=True,exist_ok=True);(root/'cache').mkdir(exist_ok=True);bins=executables(args)
    versions={c:subprocess.run([p,'--version'],capture_output=True,text=True,check=True,timeout=15).stdout.strip() for c,p in bins.items()}
    engine.EXPECTED_CLAUDE_MODEL=args.claude_model;engine.ROOT=root
    source_home=Path(os.environ.get('CODEX_HOME',str(Path.home()/'.codex'))).resolve()
    if args.fake_bin:source_home=root/'fake-source-home'
    profile=root/'profiles/codex-controlled';config={'codex_model':args.codex_model,'claude_model':args.claude_model,'effort':args.effort,'fake':bool(args.fake_bin),'executables':bins,'versions':versions,'timeout_seconds':300}
    auth=profile/'auth.json'
    try:
        mf=root/'manifest.json'
        if not mf.exists():
            for name in ('fixtures','oracle'):shutil.copytree(ROOT/name,root/name)
            make_profile(profile,source_home)
            with (profile/'config.toml').open('a') as f:
                dirs=[root/'preflight'/c/'work' for c in ('codex','claude')]
                dirs +=[root/'runs'/f"{i:02d}-{r['mode']}-{r['task']}-r{r['rep']}-{r['client']}"/'work' for i,r in enumerate(schedule(),1)]
                for d in dirs:f.write('\n[projects.'+json.dumps(str(d))+']\ntrust_level="trusted"\n')
            installed=Path(os.environ.get('CLAUDE_CONFIG_DIR',str(Path.home()/'.claude')))/'plugins/installed_plugins.json'
            plugins=json.loads(installed.read_text()).get('plugins',{}) if installed.exists() and not args.fake_bin else {}
            (root/'profiles/claude-clean.json').write_text(json.dumps({'advisorModel':'','disableAllHooks':True,'enabledPlugins':{k:False for k in plugins}},indent=2))
            paths=[p for folder in ('fixtures','oracle') for p in (root/folder).rglob('*') if p.is_file() and '__pycache__' not in p.parts]+[profile/'config.toml',root/'profiles/claude-clean.json']
            manifest={'frozen_at':engine.stamp(),'files':{str(p.relative_to(root)):engine.input_digest(p) for p in paths},'runner_source_sha256':{p:archive.digest(ROOT/p) for p in ('benchmark.py','engine.py','archive.py','reporting.py','fixtures.py')},'schedule':schedule(),'models':{'codex':args.codex_model,'claude':args.claude_model},'cli_versions':versions,'timeout_seconds':300,'configuration':config}
            mf.write_text(json.dumps(manifest,indent=2))
        else:
            manifest=json.loads(mf.read_text())
            if manifest['configuration']!=config:raise ValueError('Resume configuration or CLI version changed')
            check_frozen(root,manifest)
            auth=profile/'auth.json'
            if not auth.exists() and (source_home/'auth.json').is_file():auth.symlink_to((source_home/'auth.json').resolve())
        file=root/'results.jsonl';previous=[json.loads(x) for x in file.read_text().splitlines()] if file.exists() else []
        if any(engine.isolation_errors(x['client'],x) for x in previous):raise ValueError('Prior isolation failure; no new model requests')
        qualify(root,args,bins)
        if args.probe_only:return
        done={x['run_id'] for x in previous};auth_blocked={x['client'] for x in previous if x.get('auth_blocked')}
        for index,row in enumerate(manifest['schedule'],1):
            rid=f"{index:02d}-{row['mode']}-{row['task']}-r{row['rep']}-{row['client']}"
            if rid in done:continue
            check_frozen(root,manifest);logs=root/'runs'/rid;work=logs/'work'
            if logs.exists():raise ValueError('Unrecorded run exists; audit without automatic retry: '+rid)
            if row['client'] in auth_blocked:raise ValueError('Prior authentication failure; no login or repeat request')
            shutil.copytree(root/'fixtures'/row['task'],work);subprocess.run(['git','init','--quiet'],cwd=work,check=True)
            print(json.dumps({'event':'start','run_id':rid}),flush=True)
            env=client_env(row['client'],root,bool(args.fake_bin))
            r=engine.run_process(command(row['client'],root,logs,bins,args),work,logs,300,env=env,prompt=(work/'TASK.md').read_text(),capture_events=True)
            r.update(engine.event_summary(row['client'],logs/'stdout.jsonl'));r.update(engine.validate_run(row['task'],work,logs,env))
            if not args.fake_bin and row['client']=='codex':
                try:r.update(check_codex_context(root,logs/'stdout.jsonl'))
                except ValueError as error:
                    r['context_violation']=True;r['errors'].append(str(error))
            r['errors']+=engine.model_errors(row['client'],r)+['client error: '+str(x) for x in r.get('client_errors',[])]
            if row['client']=='codex' and not any(e.get('type')=='turn.completed' for e in read_events(logs/'stdout.jsonl')):r['errors'].append('Codex completed turn not proven')
            raw=(logs/'stdout.jsonl').read_text(errors='replace')+(logs/'stderr.log').read_text(errors='replace')
            if any(t in raw.lower() for t in ('not logged in','please run /login','authentication_error','missing bearer')):r['auth_blocked']=True;auth_blocked.add(row['client'])
            r.update(row,index=index,run_id=rid);r['latency']=latency(logs)
            started=r.pop('started_monotonic');r['total_seconds']=time.monotonic()-started;r['passed']=r['status']=='ok' and not r['errors']
            (logs/'result.json').write_text(json.dumps(r,ensure_ascii=False,indent=2))
            with file.open('a') as f:f.write(json.dumps(r,ensure_ascii=False)+'\n');f.flush();os.fsync(f.fileno())
            print(json.dumps({'event':'done','run_id':rid,'passed':r['passed']}),flush=True)
            if engine.isolation_errors(row['client'],r):raise ValueError('Isolation failure; further requests stopped')
    finally:
        if auth.is_symlink():auth.unlink()


def main(argv=None):
    parser=argparse.ArgumentParser(description=__doc__)
    parser.add_argument('action',choices=('verify','report','run','export'))
    parser.add_argument('--output-dir',type=Path);parser.add_argument('--dataset',default='all');parser.add_argument('--source',type=Path)
    parser.add_argument('--resume',action='store_true');parser.add_argument('--probe-only',action='store_true')
    parser.add_argument('--codex-bin');parser.add_argument('--claude-bin')
    parser.add_argument('--codex-model',default='gpt-6.1-sol');parser.add_argument('--claude-model',default='claude-opus-5-5');parser.add_argument('--effort',default='high',choices=('low','medium','high','xhigh'))
    group=parser.add_mutually_exclusive_group();group.add_argument('--real',action='store_true');group.add_argument('--fake-bin',type=Path)
    args=parser.parse_args(argv)
    if args.action=='run':
        if not args.real and args.fake_bin is None:parser.error('run requires --real or --fake-bin')
        if not args.output_dir:parser.error('run requires --output-dir')
        run(args)
    elif args.action=='export':
        if not args.source or not args.output_dir or args.dataset=='all':parser.error('export requires --source, --output-dir and --dataset ID')
        archive.export_series(args.source,args.output_dir,args.dataset)
    else:
        datasets=sorted(p for p in (ROOT/'datasets').iterdir() if p.is_dir()) if args.dataset=='all' else [ROOT/'datasets'/args.dataset]
        if args.action=='verify':
            for p in datasets:print(json.dumps(reporting.verify_dataset(p)),flush=True)
        else:print(json.dumps(reporting.render(datasets,args.output_dir or ROOT/'reports')))


if __name__=='__main__':
    try:main()
    except (ValueError,OSError,subprocess.SubprocessError) as e:
        print(str(e),file=sys.stderr);sys.exit(1)
