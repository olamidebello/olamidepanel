"""Root-only deployment wrapper; reuse the verified runuser provisioning path."""
import json, os, subprocess, sys

def provision(credentials, database, runner=subprocess.run):
    account={'username':credentials['panel_admin_username'], 'password':credentials['panel_admin_password'], 'role':'root', 'active':True}
    result=runner(['runuser','-u','olamidepanel','--','/opt/olamidepanel/venv/bin/python','/opt/olamidepanel/panel/server.py','--provision-user'],
                  input=json.dumps(account),text=True,capture_output=True,
                  cwd='/tmp',env={**os.environ,'PANEL_DATA':'/var/lib/olamidepanel','PANEL_DB_CONFIG':'/etc/olamidepanel/database.json'})
    if result.returncode:
        error=(result.stderr or result.stdout or 'Provisioning failed')[-3000:]
        for values in [credentials,database]:
            for key,value in values.items():
                if 'password' in key and isinstance(value,str) and value:error=error.replace(value,'[REDACTED]')
        return {'changed':False,'ok':False,'error':error,'exit_code':result.returncode}
    try: changed=bool(json.loads(result.stdout)['changed'])
    except (ValueError,KeyError):return {'changed':False,'ok':False,'error':'Unexpected response from provisioning CLI'}
    return {'changed':changed,'ok':True}

if __name__=='__main__':
    try:
        with open('/etc/olamidepanel/bootstrap-credentials.json') as f:credentials=json.load(f)
        with open('/etc/olamidepanel/database.json') as f:database=json.load(f)
        output=provision(credentials,database)
    except Exception as e:
        output={'ok':False,'changed':False,'error':'Bootstrap wrapper failed: '+type(e).__name__}
    print(json.dumps(output))
    sys.exit(0 if output['ok'] else 1)
