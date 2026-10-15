"""Export benchmark evidence without account data or native instruction contexts."""
from collections import Counter
from datetime import datetime
import hashlib
import json
from pathlib import Path
import re
import shutil
import tomllib
from urllib.parse import urlsplit

PUBLIC_DOMAINS = {'github.com', 'raw.githubusercontent.com', 'developers.openai.com', 'platform.openai.com', 'docs.anthropic.com', 'code.claude.com'}


def digest(path):
    return hashlib.sha256(Path(path).read_bytes()).hexdigest()


def sanitize_text(text):
    text = re.sub(r'https?://[^\s<>\"\x27)]+', lambda m: m[0] if urlsplit(m[0]).hostname in PUBLIC_DOMAINS else '<PRIVATE_URL>', text)
    text = re.sub(r'/(?:Users|home)/[^/\s\"\x27\\]+', '<HOME>', text)
    text = re.sub(r'(?:/private)?/var/folders/[^\s\"\x27]+', '<TEMP>', text)
    text = re.sub(r'\b(?:[a-zA-Z0-9-]+\.)*(?:wl\.tech|infra4\.dev)\b', '<PRIVATE_HOST>', text)
    text = re.sub(r'\b[\w.+-]+@[\w.-]+\.[a-zA-Z]{2,}\b', '<EMAIL>', text)
    text = re.sub(r'\b[0-9a-fA-F]{8}(?:-[0-9a-fA-F]{4}){3}-[0-9a-fA-F]{12}\b', lambda m: 'id-'+hashlib.sha256(m[0].encode()).hexdigest()[:12], text)
    return text


def clean(value):
    if isinstance(value, str):return sanitize_text(value)
    if isinstance(value, list):return [clean(x) for x in value]
    if isinstance(value, dict):return {sanitize_text(k):clean(v) for k,v in value.items()}
    return value


def numeric(value):
    if isinstance(value, dict):return {k:numeric(v) for k,v in value.items() if isinstance(v,(int,float,dict))}
    return value


def public_event(event):
    """Allow-list metadata. Tool output, instructions and tool input bodies are omitted."""
    if not isinstance(event, dict):return None
    kind = event.get('type')
    if kind not in {'system','assistant','user','result','thread.started','turn.started','turn.completed','turn.failed','error','item.started','item.completed'}:
        return None
    out = {k:clean(event[k]) for k in ('type','subtype','timestamp','model','claude_code_version','is_error','duration_ms','duration_api_ms','num_turns','total_cost_usd','fast_mode_state','per_turn_effort_active','message','error') if k in event and k != 'message'}
    for k in ('usage','modelUsage'):
        if isinstance(event.get(k),dict):out[k]=numeric(event[k])
    if kind == 'system' and event.get('subtype') == 'init':
        out['tools'] = event.get('tools',[])
        out['plugins'] = [{'path':'builtin' if p.get('path')=='builtin' else '<USER_PLUGIN>',
                           'name':p.get('name','builtin') if p.get('path')=='builtin' else '<USER_PLUGIN>'} for p in event.get('plugins',[]) or [] if isinstance(p,dict)]
        out['mcp_server_count'] = len(event.get('mcp_servers',[]) or [])
    if kind == 'assistant':
        msg = event.get('message',{});contents=[]
        for b in msg.get('content',[]):
            if b.get('type') == 'text':contents.append({'type':'text','text':sanitize_text(b.get('text',''))})
            elif b.get('type') in {'tool_use','server_tool_use'}:
                contents.append({'type':b['type'],'name':b.get('name'),'input_omitted':True})
        out['message']={k:msg[k] for k in ('role','model') if k in msg}
        out['message']['content']=contents
        if isinstance(msg.get('usage'),dict):out['message']['usage']=numeric(msg['usage'])
        out['is_main_assistant']=event.get('parent_tool_use_id') is None
    if kind == 'user':
        out['tool_result_omitted']=True
    if kind in {'item.started','item.completed'}:
        item=event.get('item',{})
        out['item']={k:clean(item[k]) for k in ('type','id','status','exit_code') if k in item}
        if item.get('type') in {'agent_message','error'}:
            for k in ('text','message'):
                if k in item:out['item'][k]=sanitize_text(item[k])
    if kind in {'error','turn.failed'} and isinstance(event.get('message'),str):out['message']=sanitize_text(event['message'])
    if kind == 'result' and isinstance(event.get('result'),str):out['result']=sanitize_text(event['result'])
    return out


def seal(root):
    root=Path(root)
    files={str(p.relative_to(root)):digest(p) for p in sorted(root.rglob('*')) if p.is_file() and not p.is_symlink() and p.name!='public-manifest.json'}
    (root/'public-manifest.json').write_text(json.dumps({'schema_version':1,'files':files},indent=2)+'\n')
    return files


def verify_hashes(root):
    root=Path(root);expected=json.loads((root/'public-manifest.json').read_text())['files']
    actual={str(p.relative_to(root)) for p in root.rglob('*') if p.is_file() and p.name!='public-manifest.json'}
    return sorted(set(expected)^actual | {n for n,h in expected.items() if (root/n).is_symlink() or not (root/n).is_file() or digest(root/n)!=h})


def check_source(source):
    source=Path(source);m=json.loads((source/'manifest.json').read_text())
    for n,h in m['files'].items():
        p=source/n
        if p.name=='config.toml':
            v=tomllib.loads(p.read_text());v.pop('projects',None)
            actual=hashlib.sha256(json.dumps(v,sort_keys=True).encode()).hexdigest()
        else:actual=digest(p)
        if actual!=h:raise ValueError('Source input changed: '+n)
    output=source/'output-manifest.json'
    if output.exists():
        for n,h in json.loads(output.read_text())['files'].items():
            if digest(source/n)!=h:raise ValueError('Source output changed: '+n)
    return m


def first_events(row, source):
    """Historical complete-event timestamps, not token arrival times."""
    logs=source/'runs'/row['run_id'];stdout=logs/'stdout.jsonl'
    if row.get('latency',{}).get('basis')=='monotonic_received_event':return row['latency']
    result={'basis':'source_event_timestamp','first_activity_seconds':None,'first_tool_seconds':None,'coverage':'missing'}
    if not stdout.exists() or not row.get('started_at'):return result
    events=[]
    for line in stdout.read_text(errors='replace').splitlines():
        try:events.append(json.loads(line))
        except ValueError:continue
    start=datetime.fromisoformat(row['started_at'])
    def seconds(event):return (datetime.fromisoformat(event['timestamp'].replace('Z','+00:00'))-start).total_seconds()
    if row['client']=='claude':
        a=[e for e in events if e.get('type')=='assistant' and e.get('timestamp') and e.get('parent_tool_use_id') is None]
        t=[e for e in a if any(b.get('type')=='tool_use' for b in e.get('message',{}).get('content',[]))]
    else:
        tid=next((e.get('thread_id') for e in events if e.get('type')=='thread.started'),None)
        if not tid:return result
        roots=[source/'profiles/codex-controlled/sessions',Path.home()/'.codex/sessions']
        paths=[]
        for root in roots:
            paths=list(root.rglob('*'+tid+'.jsonl')) if root.exists() else []
            if paths:break
        if len(paths)!=1:return result
        native=[json.loads(x) for x in paths[0].read_text().splitlines()]
        if not any(e.get('type')=='session_meta' and e.get('payload',{}).get('id')==tid for e in native):return result
        a=[e for e in native if e.get('type')=='response_item' and (e.get('payload',{}).get('type') in {'function_call','custom_tool_call'} or (e.get('payload',{}).get('type')=='message' and e['payload'].get('role')=='assistant'))]
        t=[e for e in a if e['payload'].get('type') in {'function_call','custom_tool_call'}]
    if a:result.update(first_activity_seconds=seconds(a[0]),first_activity_at=a[0]['timestamp'])
    if t:result.update(first_tool_seconds=seconds(t[0]),first_tool_at=t[0]['timestamp'])
    if a and t:result['coverage']='available'
    return result


ROW_FIELDS = set("""
advisor_calls auth_blocked cleanup_verified client client_errors client_seconds command
context_violation counted_in_60_launch_budget errors finished_at hook_events index isolation_evidence_complete
load_after load_before main_models mode observed_models passed rep
reported_versions returncode run_id started_at status task tool_calls
total_seconds usage validation_seconds
""".split())
WORK_NAMES = {'records.go','records_test.go','go.mod','aggregate.py','test_visible.py','result.md','result.json'}


def export_series(source, destination, dataset_id):
    source=Path(source);destination=Path(destination)
    if destination.exists():raise ValueError('Export destination already exists')
    m=check_source(source);destination.mkdir(parents=True)
    origins={};omitted=Counter()
    def copy_text(p,rel):
        if p.is_symlink():raise ValueError('Refusing source symlink: '+str(rel))
        text=p.read_text();target=destination/rel;target.parent.mkdir(parents=True,exist_ok=True)
        target.write_text(sanitize_text(text));origins[str(rel)]=digest(p)
    for name in ('fixtures','oracle'):
        root=source/name
        if root.exists():
            for p in sorted(root.rglob('*')):
                if p.is_file() and '__pycache__' not in p.parts:copy_text(p,p.relative_to(source))
    for name in ('benchmark.py','fixtures.py','test_benchmark.py','qualify.py','detailed_report.py'):
        p=source/name
        if p.exists():copy_text(p,Path('snapshots')/(name+'.txt'))
    rows=[]
    for original in map(json.loads,(source/'results.jsonl').read_text().splitlines()):
        row=clean({k:v for k,v in original.items() if k in ROW_FIELDS})
        row['latency']=first_events(original,source)
        if original['status']=='invalid_protocol':row['exclusion_reason']='Accidental real CLI request during fake qualification before protocol fixes; no retry.'
        rows.append(row)
        logs=source/'runs'/original['run_id']
        if not logs.exists():continue
        out=destination/'runs'/original['run_id'];out.mkdir(parents=True)
        stdout=logs/'stdout.jsonl'
        if stdout.exists():
            public=[]
            for line_number,line in enumerate(stdout.read_text(errors='replace').splitlines(),1):
                try:event=json.loads(line)
                except ValueError:omitted['malformed_event_lines']+=1;continue
                value=public_event(event)
                if value is None:omitted['event_type:'+str(event.get('type'))]+=1
                else:
                    value['source_line']=line_number;public.append(value)
            (out/'events.public.jsonl').write_text(''.join(json.dumps(x,ensure_ascii=False)+'\n' for x in public))
            origins[str((out/'events.public.jsonl').relative_to(destination))]=digest(stdout)
        for rel in ('stderr.log','final.txt','events-timing.jsonl','validation/stdout.jsonl','validation/stderr.log'):
            p=logs/rel
            if p.is_file():
                target=(out/rel).relative_to(destination)
                if rel=='validation/stdout.jsonl' and original['status']=='invalid_protocol':
                    try:
                        for line in p.read_text().splitlines():json.loads(line)
                    except ValueError:target=target.with_suffix('.txt')
                copy_text(p,target)
        work=logs/'work'
        if work.exists():
            for p in work.iterdir():
                if p.is_file() and (p.name in WORK_NAMES or p.name.endswith('_test.go') or p.name.startswith('test_') and p.suffix=='.py'):
                    copy_text(p,(out/'work'/p.name).relative_to(destination))
    (destination/'results.jsonl').write_text(''.join(json.dumps(x,ensure_ascii=False)+'\n' for x in rows))
    metadata={'schema_version':1,'dataset_id':dataset_id,'attempts':len(rows),'source_manifest_sha256':digest(source/'manifest.json'),
              'source_output_manifest_sha256':digest(source/'output-manifest.json') if (source/'output-manifest.json').exists() else None,
              'original_manifest':clean(m),'timing_note':'First complete recorded model event or tool call. Historical source timestamps, not TTFT.',
              'historical_profiles':{'controlled':'high effort for both clients','native':'Codex high, Claude xhigh with user extensions; not a portable baseline'},
              'publication_note':'Filtered public evidence. Original source hashes and public artifact hashes have separate meanings.'}
    (destination/'dataset.json').write_text(json.dumps(metadata,ensure_ascii=False,indent=2)+'\n')
    (destination/'source-provenance.json').write_text(json.dumps({'original_file_sha256':origins,'source_archives_unchanged':True},indent=2)+'\n')
    preflight=source/'isolation-preflight.json'
    if preflight.exists():
        x=json.loads(preflight.read_text());safe={k:x[k] for k in ('at','customization_free','advisor_disabled','probes','scored','real_requests') if k in x}
        (destination/'preflight.public.json').write_text(json.dumps(safe,ensure_ascii=False,indent=2)+'\n')
    exclusions={'omitted_event_counts':dict(omitted),'removed_categories':['credentials and auth files','account identifiers and subscription quotas','request/session IDs','native system/developer instruction contexts and reasoning','tool input bodies and tool output bodies in model traces','private tracking records, local profile inventories, Git history, caches and plugin state'],
                'redacted_categories':['home paths','private URLs and hostnames','email addresses','UUID values'],
                'preserved_categories':['synthetic prompts and inputs','model solution files','external acceptance stdout/stderr','attempt status and timing','token usage and model identity fields','source hash commitments']}
    (destination/'redactions.json').write_text(json.dumps(exclusions,indent=2)+'\n')
    seal(destination)
    return rows
