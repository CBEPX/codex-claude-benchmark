"""Process supervision and the historical synthetic acceptance rules."""
from datetime import datetime
import hashlib
import json
import os
from pathlib import Path
import re
import selectors
import shutil
import signal
import subprocess
import sys
import time
import tomllib
from zoneinfo import ZoneInfo
ROOT = Path(__file__).resolve().parent
EXPECTED_CLAUDE_MODEL = 'claude-opus-5-5'

def stamp():
    return datetime.now(ZoneInfo('Europe/Moscow')).isoformat()

def process_table():
    p=subprocess.run(['ps','-axo','pid=,ppid=,pgid=,lstart=,stat=,comm='],capture_output=True,text=True,check=True)
    result={}
    for line in p.stdout.splitlines():
        fields=line.split(None,9)
        if len(fields)!=10:continue
        result[int(fields[0])]=dict(ppid=int(fields[1]),pgid=int(fields[2]),
            start=' '.join(fields[3:8]),state=fields[8],executable=fields[9])
    return result

def validate_prose(text, spec):
    words = len(text.split())
    errors = []
    if not spec['min_words'] <= words <= spec['max_words']:
        errors.append(f"words={words}, expected {spec['min_words']}..{spec['max_words']}")
    for value in spec['protected'] + spec.get('headings', []):
        if value not in text:
            errors.append('missing protected fragment: ' + value)
    for value in spec.get('forbidden', []):
        if value.casefold() in text.casefold():
            errors.append('contradiction: ' + value)
    headings=spec.get('headings',[])
    if spec.get('formal_version') == 2:
        if '<!--' in text:errors.append('HTML comments are forbidden')
        numbers=lambda value:set(re.findall(r'\d+(?:[.,]\d+)*',value))
        if numbers(text)-numbers(' '.join(spec['protected'])):
            errors.append('new numeric literal')
        sections=[];commands=[];current=None;fence=None
        for line in text.splitlines():
            stripped=line.strip()
            marker=re.match(r'^(`{3,}|~{3,})',stripped)
            if marker:
                token=marker[1]
                if fence is None:fence=token
                elif token[0]==fence[0] and len(token)>=len(fence) and stripped==token:fence=None
                continue
            if fence is None and re.match(r'^##(?:\s|$)',line):
                current=line.rstrip();sections.append(current)
            if 'northctl' in line and spec.get('command_sections'):
                commands.append((stripped.strip('`'),current))
        if headings and sections!=headings:
            errors.append('expected exact ordered level-two headings')
        if spec.get('command_sections') and commands!=list(spec['command_sections'].items()):
            errors.append('expected exact ordered commands in their required sections')
    else:
        for command, heading in spec.get('command_sections',{}).items():
            index=headings.index(heading)
            begin=text.find(heading)
            end=text.find(headings[index+1]) if index+1<len(headings) else len(text)
            position=text.find(command)
            if begin<0 or position<begin or position>=end:
                errors.append('command outside required section: '+command)
    return errors

def validate_search(answer, expected):
    strict=isinstance(expected,dict) and expected.get('formal_version')==2
    if strict:expected=expected['answers']
    if not isinstance(answer, list):
        return ['expected a JSON array']
    if len(answer) != len(expected):
        return ['wrong answer count']
    errors = []
    for got, want in zip(answer, expected):
        valid=isinstance(got,dict)
        if strict:valid=valid and type(got.get('id')) is int and isinstance(got.get('answer'),str) and isinstance(got.get('evidence'),list)
        if valid and strict:
            valid=all(isinstance(e,dict) and isinstance(e.get('file'),str) and type(e.get('line')) is int for e in got['evidence'])
        if not valid or any(got.get(k) != want[k] for k in ('id', 'answer', 'evidence')):
            errors.append(f"wrong answer or source for question {want['id']}")
    return errors

def event_summary(client, path):
    models, main_models, usage, calls, versions = set(), set(), None, 0, set()
    advisor_calls, hook_events, user_plugins, mcp_servers = 0, 0, [], []
    init_valid, result_valid, malformed = False, False, False
    errors = []
    for line in Path(path).read_text(errors='replace').splitlines():
        try:
            event = json.loads(line)
        except ValueError:
            malformed = True
            continue
        if not isinstance(event, dict):
            malformed = True
            continue
        if client == 'claude':
            if event.get('type') == 'system' and event.get('subtype') == 'init':
                plugins, servers = event.get('plugins'), event.get('mcp_servers')
                init_valid = (isinstance(plugins, list) and all(isinstance(x, dict) for x in plugins)
                              and isinstance(servers, list))
                user_plugins = [x.get('source', x.get('name')) for x in (plugins or []) if isinstance(x, dict)
                                if x.get('path') != 'builtin']
                mcp_servers = servers or []
                if event.get('model'):
                    models.add(event['model'])
                if event.get('claude_code_version'):
                    versions.add(event['claude_code_version'])
            message = event.get('message', {})
            if event.get('type') == 'assistant':
                advisor_calls += sum(x.get('type') == 'server_tool_use' for x in message.get('content', []))
                if message.get('model'):
                    models.add(message['model'])
                    if event.get('parent_tool_use_id') is None:main_models.add(message['model'])
                calls += sum(x.get('type') == 'tool_use' for x in message.get('content', []))
            if event.get('type') == 'system' and event.get('subtype', '').startswith('hook_'):
                hook_events += 1
            if event.get('type') == 'result':
                result_valid = (event.get('subtype') == 'success' and event.get('is_error') is False
                                and isinstance(event.get('modelUsage'), dict) and bool(event['modelUsage']))
                usage = event.get('usage')
                models.update(event.get('modelUsage', {}))
                if event.get('is_error'):
                    errors.extend(event.get('errors', []) or [event.get('subtype', 'error')])
        else:
            if event.get('type') == 'turn.completed':
                current = event.get('usage', {})
                usage = {key: (usage or {}).get(key, 0) + value for key, value in current.items()
                         if isinstance(value, (int, float))}
            if event.get('type') == 'item.completed':
                calls += event.get('item', {}).get('type') in {'command_execution', 'mcp_tool_call', 'web_search', 'file_change'}
            if event.get('type') in {'error', 'turn.failed'}:
                errors.append(str(event.get('message', event.get('error', 'error'))))
    return dict(observed_models=sorted(models), main_models=sorted(main_models), usage=usage, tool_calls=calls,
                advisor_calls=advisor_calls, hook_events=hook_events, user_plugins=user_plugins, mcp_servers=mcp_servers,
                isolation_evidence_complete=init_valid and result_valid and not malformed,
                reported_versions=sorted(versions), client_errors=errors)

def isolation_errors(client, summary):
    if (summary.get('status') == 'cleanup_error' or summary.get('cleanup_verified') is False
            or summary.get('validation_cleanup_verified') is False or summary.get('postprocessing_failed')):
        return ['clean isolation evidence failed: cleanup or result processing unverified']
    if summary.get('context_violation'):
        return ['clean isolation evidence failed: session context invalid or customized']
    if client != 'claude':
        return []
    if summary.get('status') == 'ok' and not summary.get('isolation_evidence_complete'):
        return ['clean isolation evidence incomplete for completed Claude run']
    if (summary.get('advisor_calls') or summary.get('hook_events') or summary.get('user_plugins')
            or summary.get('mcp_servers') or any(x != EXPECTED_CLAUDE_MODEL for x in summary.get('observed_models', []))):
        return ['clean isolation violated: advisor/helper model/hooks/user plugin/MCP present']
    return []

def model_errors(client, summary):
    if client == 'claude' and not summary.get('isolation_evidence_complete'):
        return ['complete Claude init/plugins/MCP/result evidence not proven']
    if client=='claude' and summary.get('main_models')!=[EXPECTED_CLAUDE_MODEL]:
        return ['expected exact main assistant model claude-opus-5-5 not proven']
    return isolation_errors(client, summary)

def digest(path):
    return hashlib.sha256(path.read_bytes()).hexdigest()

def input_digest(path):
    if path.name=='config.toml':
        data=tomllib.loads(path.read_text())
        data.pop('projects',None)  # CLI-maintained per-directory trust cache; not a model/feature setting.
        return hashlib.sha256(json.dumps(data,sort_keys=True).encode()).hexdigest()
    return digest(path)

def validate_run(task, work, logs, env):
    start = time.monotonic()
    errors = []
    validation_cleanup_verified = True
    original = ROOT/'fixtures'/task
    for p in original.rglob('*'):
        if not p.is_file() or p.name in {'records.go', 'aggregate.py'}:
            continue
        candidate = work/p.relative_to(original)
        if not candidate.is_file() or digest(candidate) != digest(p):
            errors.append('immutable input changed: '+str(p.relative_to(original)))
    if task in {'go', 'python'}:
        name = 'acceptance_test.go' if task == 'go' else 'test_acceptance.py'
        verifier=logs/'validation-work';verifier.mkdir(parents=True)
        source='records.go' if task=='go' else 'aggregate.py'
        if not (work/source).is_file():
            errors.append('external acceptance tests: missing model artifact '+source)
            return dict(errors=errors,validation_seconds=time.monotonic()-start)
        shutil.copy2(work/source,verifier/source)
        visible=['go.mod','records_test.go'] if task=='go' else ['test_visible.py']
        for value in visible:shutil.copy2(original/value,verifier/value)
        shutil.copy2(ROOT/'oracle'/name, verifier/name)
        command = ['go','test','-json','-count=1','./...'] if task == 'go' else [sys.executable,'-I','-m','unittest','discover','-v']
        checked = run_process(command, verifier, logs/'validation', 45, env=env)
        validation_cleanup_verified = checked.get('cleanup_verified') is True
        if checked['status'] != 'ok':
            errors.append('external acceptance tests: '+checked['status'])
        stdout=(logs/'validation/stdout.jsonl').read_text()
        stderr=(logs/'validation/stderr.log').read_text()
        if task=='go':
            completed=set()
            for line in stdout.splitlines():
                try:event=json.loads(line)
                except ValueError:continue
                if event.get('Action')=='pass' and event.get('Test'):completed.add(event['Test'])
            if not {'TestBasic','TestDeduplicate','TestAcceptance'}<=completed:
                errors.append('external Go test completion proof missing')
        elif not re.search(r'Ran 10 tests? in ',stderr) or not re.search(r'^OK$',stderr,re.M):
            errors.append('external Python test completion proof missing')
    else:
        name = 'result.json' if task == 'search' else 'result.md'
        try:
            text = (work/name).read_text()
            spec = json.loads((ROOT/'oracle'/f'{task}.json').read_text())
            if task == 'search':
                errors += validate_search(json.loads(text), spec)
            else:
                errors += validate_prose(text, spec)
                if task == 'write':
                    from fixtures import COMMANDS, HEADINGS
                    for values in (COMMANDS, HEADINGS):
                        positions = [text.find(x) for x in values]
                        if -1 in positions or positions != sorted(positions):
                            errors.append('required order changed')
        except (OSError, ValueError) as error:
            errors.append(str(error))
    return dict(errors=errors, validation_seconds=time.monotonic()-start,validation_cleanup_verified=validation_cleanup_verified)


def event_activity(event):
    if event.get('type')=='assistant' and event.get('parent_tool_use_id') is None:
        blocks=event.get('message',{}).get('content',[])
        tool=any(x.get('type') in {'tool_use','server_tool_use'} for x in blocks)
        return tool or any(x.get('type')=='text' and x.get('text') for x in blocks),tool
    item=event.get('item',{});kind=item.get('type')
    tool=kind in {'command_execution','mcp_tool_call','web_search','file_change'}
    return (event.get('type') in {'item.started','item.completed'} and (tool or kind=='agent_message')),tool


def run_process(command,cwd,output_dir,timeout,*,env=None,prompt='',capture_events=False):
    output_dir=Path(output_dir);output_dir.mkdir(parents=True,exist_ok=True)
    start=time.monotonic();r={'command':command,'started_at':stamp(),'started_monotonic':start,'load_before':os.getloadavg()}
    owned={};pending=bytearray();line_number=0;stdin_data=memoryview(prompt.encode());sent=0;eof=False
    with (output_dir/'stdout.jsonl').open('wb') as out,(output_dir/'stderr.log').open('wb') as err:
        timing=(output_dir/'events-timing.jsonl').open('w') if capture_events else None
        proc=subprocess.Popen(command,cwd=cwd,env=env,stdin=subprocess.PIPE,stdout=subprocess.PIPE,stderr=err,start_new_session=True)
        r['pid']=proc.pid;os.set_blocking(proc.stdout.fileno(),False);os.set_blocking(proc.stdin.fileno(),False)
        selector=selectors.DefaultSelector();selector.register(proc.stdout,selectors.EVENT_READ)
        def observe():
            table=process_table();parents=set(owned)|{proc.pid};changed=True
            while changed:
                changed=False
                for pid,info in table.items():
                    if (pid==proc.pid or info['ppid'] in parents) and pid not in owned:
                        owned[pid]=info;parents.add(pid);changed=True
            return table
        def record(line):
            nonlocal line_number
            line_number+=1
            if timing:
                try:event=json.loads(line)
                except (ValueError,UnicodeError):event={}
                if not isinstance(event,dict):event={}
                activity,tool=event_activity(event)
                timing.write(json.dumps({'source_line':line_number,'elapsed_seconds':time.monotonic()-start,'type':event.get('type'),'activity':bool(activity),'tool':bool(tool)})+'\n');timing.flush()
        def drain():
            nonlocal eof
            while not eof:
                try:chunk=os.read(proc.stdout.fileno(),65536)
                except BlockingIOError:break
                if not chunk:eof=True;break
                out.write(chunk);out.flush();pending.extend(chunk)
                while b'\n' in pending:
                    line,_,rest=pending.partition(b'\n');pending[:]=rest;record(line)
        def signal_owned(sig):
            table=process_table()
            for pid,info in owned.items():
                v=table.get(pid)
                if v and v['start']==info['start'] and not v['state'].startswith('Z'):
                    try:os.kill(pid,sig)
                    except ProcessLookupError:pass
        try:
            while True:
                observe()
                if not proc.stdin.closed:
                    try:
                        if sent<len(stdin_data):sent+=os.write(proc.stdin.fileno(),stdin_data[sent:])
                        if sent==len(stdin_data):proc.stdin.close()
                    except BlockingIOError:pass
                    except BrokenPipeError:proc.stdin.close()
                drain()
                if proc.poll() is not None:r['status']='ok' if proc.returncode==0 else 'error';break
                remaining=start+timeout-time.monotonic()
                if remaining<=0:r['status']='timeout';break
                selector.select(min(.05,remaining))
        finally:
            observe()
            try:os.killpg(proc.pid,signal.SIGTERM);r['group_cleanup_sent']=True
            except ProcessLookupError:r['group_cleanup_sent']=False
            signal_owned(signal.SIGTERM)
            try:proc.wait(timeout=2)
            except subprocess.TimeoutExpired:pass
            try:os.killpg(proc.pid,signal.SIGKILL)
            except ProcessLookupError:pass
            signal_owned(signal.SIGKILL);proc.wait();drain()
            if pending:record(bytes(pending))
            selector.close();proc.stdout.close()
            if not proc.stdin.closed:proc.stdin.close()
            if timing:timing.close()
            r['returncode']=proc.returncode;table=process_table()
            r['owned_processes']=[dict(pid=p,**v) for p,v in owned.items()]
            r['surviving_observed_pids']=[p for p,v in owned.items() if p in table and table[p]['start']==v['start'] and not table[p]['state'].startswith('Z')]
            r['cleanup_verified']=not r['surviving_observed_pids'] and eof
            if not r['cleanup_verified']:r['status']='cleanup_error'
    r.update(client_seconds=time.monotonic()-start,finished_at=stamp(),load_after=os.getloadavg())
    return r
