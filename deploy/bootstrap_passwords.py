"""Generate persistent initial secrets; stdout MUST be protected by Ansible no_log."""
import json, os, secrets, sys, tempfile
from pathlib import Path

FIELDS={'panel_mysql_root_password':20,'panel_mysql_password':20,'panel_admin_password':14}

def valid(value, minimum):
    return isinstance(value,str) and len(value)>=minimum and 'REPLACE_WITH' not in value and 'YOUR_' not in value

def prepare(path, supplied):
    path=Path(path)
    if path.is_symlink(): raise ValueError('Bootstrap path must not be a symbolic link')
    saved=json.loads(path.read_text()) if path.exists() else {}
    result={}
    for field,minimum in FIELDS.items():
        value=supplied.get(field)
        if not valid(value,minimum): value=saved.get(field)
        if not valid(value,minimum): value=secrets.token_urlsafe(32)
        result[field]=value
    result['panel_admin_username']=supplied.get('panel_admin_username','owner')
    if result!=saved:
        descriptor,tmp=tempfile.mkstemp(dir=path.parent,prefix='.bootstrap-')
        try:
            with os.fdopen(descriptor,'w') as stream: json.dump(result,stream);stream.write('\n')
            os.chmod(tmp,0o600);os.replace(tmp,path)
        finally:
            if os.path.exists(tmp):os.unlink(tmp)
    os.chmod(path,0o600)
    return {field.replace('panel_','panel_effective_',1):result[field] for field in FIELDS}

if __name__=='__main__':
    data=json.load(sys.stdin)
    print(json.dumps(prepare(sys.argv[1],data)))
