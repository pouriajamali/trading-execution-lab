"""Explicitly authorized private Linux prerequisites; no global installation."""
import hashlib,json,os,posixpath,shutil,tarfile,time,urllib.request
from pathlib import Path

def need(ok,why):
    if not ok:raise RuntimeError(why)

def sha(path):
    with Path(path).open('rb') as stream:return hashlib.file_digest(stream,'sha256').hexdigest()

def acquire(root,work):
    lock=root/'tools/local-linux-tools.lock.json';data=json.loads(lock.read_bytes());dest=root/'artifacts/linux-tool-inputs';dest.mkdir(parents=True,exist_ok=True);outputs=[];started=time.monotonic()
    class Redirect(urllib.request.HTTPRedirectHandler):
        def redirect_request(self,req,fp,code,msg,headers,newurl):
            from urllib.parse import urlparse
            u=urlparse(newurl);need(u.scheme=='https' and (u.hostname in ('github.com','nodejs.org','release-assets.githubusercontent.com','objects.githubusercontent.com') or u.hostname.endswith('.githubusercontent.com')),'official tool redirect only')
            return super().redirect_request(req,fp,code,msg,headers,newurl)
    opener=urllib.request.build_opener(urllib.request.ProxyHandler({}),Redirect())
    for name,row in data['tools'].items():
        target=dest/(name+'.tar.gz')
        if target.exists():need(sha(target)==row['sha256'],'retained exact tool input')
        else:
            temporary=target.with_suffix('.part');need(not temporary.exists(),'incomplete tool body retained; diagnose before retry')
            request=urllib.request.Request(row['url'],headers={'User-Agent':'own02-private-linux-tools','Accept-Encoding':'identity'})
            size=0;h=hashlib.sha256();maximum=row.get('bytes',row.get('maximumRawBytes'))
            with opener.open(request,timeout=15) as response,temporary.open('xb') as output:
                need(response.status==200 and response.headers.get('Content-Encoding','identity')=='identity','exact tool archive response')
                while chunk:=response.read(1048576):
                    size+=len(chunk);need(size<=maximum and time.monotonic()-started<170,'private tool body/time limits');h.update(chunk);output.write(chunk)
                output.flush();os.fsync(output.fileno())
            need(h.hexdigest()==row['sha256'] and ('bytes' not in row or size==row['bytes']),'official exact tool digest/size');temporary.rename(target)
        outputs.append({'name':name,'path':str(target),'bytes':target.stat().st_size,'sha256':sha(target)})
    (work/'private-tool-inputs.json').write_bytes((json.dumps({'state':'OFFICIAL_EXACT_PRIVATE_TOOL_ARCHIVES_ACQUIRED_NOT_EXECUTED','sourceLockSHA256':sha(lock),'archives':outputs,'globalChanges':False,'SDK':0},indent=2)+'\n').encode())

def materialize(root,source,guard):
    need(os.name!='nt' and os.getuid()==os.getgid()==1000,'private nonroot Linux tools only')
    lock=root/'tools/local-linux-tools.lock.json';data=json.loads(lock.read_bytes());dest=root/'artifacts/private-tools';dest.mkdir(parents=True,exist_ok=True);proofs=[]
    for name,row in data['tools'].items():
        archive=source/(name+'.tar.gz');need(sha(archive)==row['sha256'],'actual private tool input digest')
        output=dest/name;need(not output.exists(),'fresh private tool destination; no overwrite')
        inventory=guard.Inventory();regular={};links={};files=[]
        with tarfile.open(archive,'r:gz') as tar:
            members=tar.getmembers();need(len(members)<=20000,'private tool member bound')
            for x in members:
                path=guard.member_path(x.name)
                if name=='node':
                    prefix='node-v'+row['version']+'-linux-x64';need(path==prefix or path.startswith(prefix+'/'),'exact Node archive root');path=path[len(prefix):].lstrip('/')
                need(x.isdir() or x.isfile() or x.issym() or x.islnk(),'no special tool member')
                kind='directory' if x.isdir() else 'file';inventory.add(path,x.size if x.isfile() else 0,kind,x.mode)
                if x.isfile():regular[path]=x
                elif x.issym() or x.islnk():links[path]=(x.linkname,x.islnk(),x.mode)
            output.mkdir(mode=0o700)
            for path,x in regular.items():
                target=output/path;target.parent.mkdir(parents=True,exist_ok=True)
                with tar.extractfile(x) as src,target.open('xb') as dst:shutil.copyfileobj(src,dst,1048576)
                target.chmod(x.mode&0o777)
            for path,(literal,hard,mode) in links.items():
                if hard and name=='node':literal=literal.removeprefix('node-v'+row['version']+'-linux-x64/')
                resolved=guard.member_path(posixpath.normpath(literal if hard else posixpath.join(posixpath.dirname(path),literal)))
                need(resolved in regular,'tool alias must name regular internal original')
                target=output/path;target.parent.mkdir(parents=True,exist_ok=True)
                if '/bin/' in '/'+path and Path(resolved).suffix in ('.js','.mjs','.cjs'):
                    body=('#!/bin/sh\nexec "'+str(output/'bin/node')+'" "'+str(output/resolved)+'" "$@"\n').encode();target.write_bytes(body);target.chmod(0o755)
                else:shutil.copyfile(output/resolved,target);target.chmod(regular[resolved].mode&0o777)
        executable=output/('bin/node' if name=='node' else 'pwsh');executable.chmod(executable.stat().st_mode|0o100)
        for path in sorted(output.rglob('*')):
            need(not path.is_symlink(),'private tools materialized as regular files')
            if path.is_file():files.append({'path':path.relative_to(output).as_posix(),'bytes':path.stat().st_size,'sha256':sha(path),'mode':path.stat().st_mode&0o777})
        manifest=dest/(name+'-members.json');manifest.write_bytes((json.dumps(files,separators=(',',':'))+'\n').encode());proofs.append({'name':name,'root':str(output),'manifest':str(manifest),'manifestSha256':sha(manifest),'files':len(files),'executableSha256':sha(executable),'sourceArchiveSha256':row['sha256']})
    receipt=dest/'admission.json';receipt.write_bytes((json.dumps({'state':'PRIVATE_OFFICIAL_TOOL_BYTES_MATERIALIZED_NOT_EXECUTED','sourceLockSha256':sha(lock),'tools':proofs,'globalChanges':False},indent=2)+'\n').encode());return proofs

def verify(root):
    dest=root/'artifacts/private-tools';receipt=json.loads((dest/'admission.json').read_bytes());need(receipt['sourceLockSha256']==sha(root/'tools/local-linux-tools.lock.json'),'private tool current source lock')
    for tool in receipt['tools']:
        manifest=Path(tool['manifest']);need(sha(manifest)==tool['manifestSha256'],'private tool manifest identity');base=Path(tool['root']);rows=json.loads(manifest.read_bytes())
        need({p.relative_to(base).as_posix() for p in base.rglob('*') if p.is_file()}=={x['path'] for x in rows},'private tool complete current namespace')
        for row in rows:
            path=base/row['path'];need(path.is_file() and not path.is_symlink() and path.stat().st_size==row['bytes'] and sha(path)==row['sha256'],'private tool exact current bytes')
