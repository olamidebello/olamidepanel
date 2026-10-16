"""Bounded account files, safe ZIP archives and recoverable backups."""
import base64,contextlib,fcntl,io,json,os,secrets,shutil,stat,tempfile,time,zipfile
from pathlib import Path, PurePosixPath
DATA=Path(os.environ.get('PANEL_DATA','/var/lib/olamidepanel')).resolve()
FILE_MAX=8*1024**2
ARCHIVE_MAX=64*1024**2
QUOTA=250*1024**2
COUNT_MAX=10000

def home(uid):
    root=DATA/'homes'/str(int(uid));root.mkdir(parents=True,exist_ok=True,mode=0o700);return root

def path(uid,name):
    if not isinstance(name,str) or '\x00' in name:raise ValueError('Invalid path')
    root=home(uid);candidate=root/name
    if not candidate.resolve().is_relative_to(root):raise ValueError('Path is outside your account')
    for item in [candidate,*candidate.parents]:
        if item==root:break
        if item.is_symlink():raise ValueError('Symbolic links are not supported')
    if candidate.is_file() and candidate.stat().st_nlink>1:raise ValueError('Hard-linked files are not supported')
    return candidate

@contextlib.contextmanager
def lock(uid):
    folder=DATA/'locks';folder.mkdir(parents=True,exist_ok=True,mode=0o700)
    with open(folder/(str(int(uid))+'.lock'),'a') as stream:
        fcntl.flock(stream,fcntl.LOCK_EX);yield

def usage(root):
    total=count=0
    for current,dirs,files in os.walk(root,followlinks=False):
        dirs[:]=[d for d in dirs if not (Path(current)/d).is_symlink()]
        count+=len(dirs)
        if count>COUNT_MAX:raise ValueError('Account file-count limit exceeded')
        for filename in files:
            item=Path(current)/filename
            if item.is_symlink():continue
            total+=item.stat().st_size;count+=1
            if count>COUNT_MAX:raise ValueError('Account file-count limit exceeded')
    return total,count

def write(uid,target,data):
    if target==home(uid) or not target.parent.is_dir():raise ValueError('Choose a file with an existing parent folder')
    if len(data)>FILE_MAX:raise ValueError('File limit is 8 MiB')
    used,count=usage(home(uid));prior=target.stat().st_size if target.is_file() else 0
    if used-prior+len(data)>QUOTA or (not target.exists() and count>=COUNT_MAX):raise ValueError('Account storage quota exceeded')
    fd,temp=tempfile.mkstemp(dir=target.parent,prefix='.panel-write-')
    try:
        with os.fdopen(fd,'wb') as f:f.write(data)
        os.chmod(temp,0o600);os.replace(temp,target)
    finally:
        if os.path.exists(temp):os.unlink(temp)

def zip_data(root,source):
    output=io.BytesIO();entries=[source] if source.is_file() else list(source.rglob('*'))
    if len(entries)>COUNT_MAX:raise ValueError('Archive file-count limit exceeded')
    size=0
    with zipfile.ZipFile(output,'w',compression=zipfile.ZIP_DEFLATED) as archive:
        for item in entries:
            if item.is_symlink() or item.resolve()!=item.absolute():raise ValueError('Archives cannot include symbolic links')
            if item.is_dir():
                archive.write(item,item.relative_to(root).as_posix()+'/');continue
            if not item.is_file():raise ValueError('Special files are not supported')
            if item.stat().st_nlink>1:raise ValueError('Archives cannot include hard links')
            size+=item.stat().st_size
            if size>ARCHIVE_MAX:raise ValueError('Archive content limit is 64 MiB')
            archive.write(item,item.relative_to(root).as_posix())
    if len(output.getvalue())>ARCHIVE_MAX:raise ValueError('Archive is too large')
    return output.getvalue()

def extract(uid,data,destination):
    if len(data)>ARCHIVE_MAX or destination.exists() or not destination.parent.is_dir():raise ValueError('Choose an unused destination with an existing parent')
    try:archive=zipfile.ZipFile(io.BytesIO(data))
    except zipfile.BadZipFile:raise ValueError('Invalid ZIP archive') from None
    with archive:
        infos=archive.infolist();total=0;names=set()
        if len(infos)>COUNT_MAX:raise ValueError('Too many archive entries')
        for info in infos:
            name=PurePosixPath(info.filename)
            if not info.filename or '\\' in info.filename or name.is_absolute() or '..' in name.parts or '\x00' in info.filename or ':' in info.filename:raise ValueError('Unsafe archive path')
            mode=info.external_attr>>16
            if stat.S_ISLNK(mode) or (stat.S_IFMT(mode) not in [0,stat.S_IFREG,stat.S_IFDIR]):raise ValueError('Archive links/special files are not supported')
            if info.flag_bits&1:raise ValueError('Encrypted ZIP archives are not supported')
            if name.as_posix() in names:raise ValueError('Duplicate archive paths')
            names.add(name.as_posix());total+=info.file_size
            if total>ARCHIVE_MAX:raise ValueError('Expanded archive limit is 64 MiB')
        used,count=usage(home(uid))
        if used+total>QUOTA or count+len(infos)>COUNT_MAX:raise ValueError('Account quota exceeded')
        stage=Path(tempfile.mkdtemp(dir=destination.parent,prefix='.panel-extract-'))
        try:
            actual=0
            for info in infos:
                target=stage/info.filename
                if info.is_dir():target.mkdir(parents=True,exist_ok=True,mode=0o700);continue
                target.parent.mkdir(parents=True,exist_ok=True,mode=0o700)
                with archive.open(info) as source,open(target,'xb') as output:
                    while True:
                        chunk=source.read(65536)
                        if not chunk:break
                        actual+=len(chunk)
                        if actual>total or actual>ARCHIVE_MAX:raise ValueError('Archive expansion exceeded declared size')
                        output.write(chunk)
                target.chmod(0o600)
            if usage(stage)[1]+count+1>COUNT_MAX:raise ValueError('Expanded file-count limit exceeded')
            stage.rename(destination)
        except (zipfile.BadZipFile,RuntimeError,NotImplementedError):
            raise ValueError('Corrupt or unsupported ZIP archive') from None
        finally:
            if stage.exists():shutil.rmtree(stage)

def backup_dir(uid):
    folder=DATA/'backups'/str(int(uid));folder.mkdir(parents=True,exist_ok=True,mode=0o700);return folder

def handle(method,route,user,body=None):
    uid=user['id'];root=home(uid)
    from urllib.parse import urlsplit,parse_qs
    parsed=urlsplit(route);query=parse_qs(parsed.query);name=query.get('path',[''])[0]
    if method=='GET':
        with lock(uid):
            if parsed.path=='/api/storage/usage':
                used,count=usage(root);return {'used_bytes':used,'quota_bytes':QUOTA,'files':count,'file_limit':COUNT_MAX}
            if parsed.path=='/api/storage/files':
                target=path(uid,name)
                if target.is_file():
                    if target.stat().st_size>1024**2:raise ValueError('Text editing limit is 1 MiB; use Download for this file')
                    try:return {'content':target.read_text()}
                    except UnicodeError:raise ValueError('Binary file: use Download') from None
                return [{'name':p.name,'directory':p.is_dir(),'size':p.stat().st_size} for p in sorted(target.iterdir()) if not p.is_symlink()]
            if parsed.path=='/api/storage/backups':return [{'id':p.stem,'size':p.stat().st_size,'created':int(p.stat().st_mtime)} for p in sorted(backup_dir(uid).glob('*.zip'),reverse=True)]
        raise ValueError('Unknown storage operation')
    if parsed.path not in ['/api/storage/files','/api/storage/backups']:raise ValueError('Unknown storage operation')
    if user['role']=='readonly':raise PermissionError('Read-only access')
    with lock(uid):
        if parsed.path=='/api/storage/backups':
            action=body['action']
            if action=='create':
                folder=backup_dir(uid)
                if len(list(folder.glob('*.zip')))>=5:raise ValueError('Backup limit is five snapshots; delete an old snapshot first')
                data=zip_data(root,root);bid=str(int(time.time()))+'-'+secrets.token_hex(8)
                target=folder/(bid+'.zip');target.write_bytes(data);target.chmod(0o600);return {'ok':True,'id':bid}
            bid=str(body['id'])
            import re
            if not re.fullmatch(r'[0-9]+-[0-9a-f]{16}',bid):raise ValueError('Invalid backup ID')
            target=backup_dir(uid)/(bid+'.zip')
            if target.is_symlink() or not target.is_file():raise ValueError('Unknown backup')
            if action=='restore':
                if body.get('confirmed') is not True:raise ValueError('Confirm restore into a new folder')
                dest=root/('restored-'+secrets.token_hex(8));extract(uid,target.read_bytes(),dest);return {'ok':True,'folder':dest.name}
            if action=='delete':
                if body.get('confirmed') is not True:raise ValueError('Confirm backup deletion')
                target.unlink();return {'ok':True}
            raise ValueError('Unknown backup action')
        target=path(uid,body['path']);action=body['action']
        if target==root:raise ValueError('Choose a file or folder')
        if action=='mkdir':
            if usage(root)[1]>=COUNT_MAX:raise ValueError('Account file-count limit exceeded')
            target.mkdir(mode=0o700)
        elif action=='write':
            data=body['content'].encode()
            if len(data)>1024**2:raise ValueError('Text editing limit is 1 MiB')
            write(uid,target,data)
        elif action=='upload':
            try:data=base64.b64decode(body['content_base64'],validate=True)
            except (ValueError,TypeError):raise ValueError('Invalid upload encoding') from None
            if target.exists() and body.get('overwrite') is not True:raise ValueError('File exists; explicitly confirm overwrite')
            write(uid,target,data)
        elif action in ['rename','copy']:
            dest=path(uid,body['destination'])
            if not target.is_file() or dest.exists():raise ValueError('Choose a file and an unused destination')
            if action=='rename':target.rename(dest)
            else:
                if target.stat().st_size>FILE_MAX:raise ValueError('Copy limit is 8 MiB')
                write(uid,dest,target.read_bytes())
        elif action=='compress':
            dest=path(uid,body['destination'])
            if dest.exists():raise ValueError('Choose an unused archive destination')
            data=zip_data(root,target)
            used,count=usage(root)
            if used+len(data)>QUOTA or count>=COUNT_MAX:raise ValueError('Account quota exceeded')
            dest.write_bytes(data);dest.chmod(0o600)
        elif action=='extract':
            if target.stat().st_size>ARCHIVE_MAX:raise ValueError('Archive too large')
            extract(uid,target.read_bytes(),path(uid,body['destination']))
        elif action=='image':
            from PIL import Image,UnidentifiedImageError
            import warnings
            dest=path(uid,body['destination'])
            if dest.exists():raise ValueError('Choose an unused image destination')
            width=body.get('width');height=body.get('height');format_name=body.get('format','PNG')
            if type(width) is not int or type(height) is not int or not 1<=width<=4000 or not 1<=height<=4000 or format_name not in ['PNG','JPEG','WEBP']:raise ValueError('Choose dimensions 1–4000 and PNG/JPEG/WEBP')
            if target.stat().st_size>FILE_MAX:raise ValueError('Image input exceeds 8 MiB')
            Image.MAX_IMAGE_PIXELS=10000000
            with warnings.catch_warnings():
                warnings.simplefilter('error',Image.DecompressionBombWarning)
                try:
                    with Image.open(target) as image:
                        image.load();image.thumbnail((width,height));image=image.convert('RGB' if format_name=='JPEG' else 'RGBA')
                        output=io.BytesIO();image.save(output,format=format_name)
                except (UnidentifiedImageError,Image.DecompressionBombError,Image.DecompressionBombWarning,OSError):raise ValueError('Invalid or oversized image') from None
            write(uid,dest,output.getvalue())
        elif action=='delete':
            if target.is_dir():target.rmdir()
            else:target.unlink()
        else:raise ValueError('Unknown file action')
        return {'ok':True}

def download(user,route):
    from urllib.parse import urlsplit,parse_qs
    q=parse_qs(urlsplit(route).query)
    with lock(user['id']):
        if 'backup' in q:
            import re
            bid=q['backup'][0]
            if not re.fullmatch(r'[0-9]+-[0-9a-f]{16}',bid):raise ValueError('Invalid backup ID')
            target=backup_dir(user['id'])/(bid+'.zip')
        else:target=path(user['id'],q.get('path',[''])[0])
        if target.is_symlink() or not target.is_file() or target.stat().st_size>ARCHIVE_MAX:raise ValueError('Invalid or oversized download')
        return target.name,target.read_bytes()
