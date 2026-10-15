"""Check public evidence for account fields and unredacted local addresses."""
import json
from pathlib import Path
import re
import sys

PRIVATE_FIELDS={'creator_account_id','creator_user_id','account_id','apiKeySource','apiKey','api_key','authorization','access_token','refresh_token','claudeAiOauth'}
PATTERNS={'home path':r'/(?:Users|home)/[A-Za-z0-9._-]+','private temporary path':r'(?:/private)?/var/folders/',
          'private GitLab URL':r'https?://gitlab\.(?!com\b)[^/\s]+','private hostname':r'\b(?:[\w-]+\.)*(?:wl\.tech|infra4\.dev)\b'}


def issues(root):
    root=Path(root);found=[]
    for folder in ('datasets','fixtures','oracle','published','validation'):
        for path in (root/folder).rglob('*'):
            if not path.is_file() or '__pycache__' in path.parts:continue
            rel=str(path.relative_to(root))
            if path.is_symlink() or path.name in {'auth.json','settings.json','credentials.json'}:
                found.append(rel+': forbidden file');continue
            text=path.read_text(errors='replace')
            for label,pattern in PATTERNS.items():
                if re.search(pattern,text):found.append(rel+': '+label)
            if path.suffix not in {'.json','.jsonl'}:continue
            def visit(value):
                if isinstance(value,dict):
                    for key,item in value.items():
                        if key in PRIVATE_FIELDS:found.append(rel+': private field '+key)
                        visit(item)
                elif isinstance(value,list):
                    for item in value:visit(item)
            try:
                if path.suffix=='.json':visit(json.loads(text))
                else:
                    for line in text.splitlines():visit(json.loads(line))
            except ValueError:found.append(rel+': malformed JSON evidence')
    return found


if __name__=='__main__':
    found=issues(Path(__file__).resolve().parent)
    print(json.dumps({'issues':found,'count':len(found)}))
    sys.exit(bool(found))
