"""Explicitly authorized private Linux prerequisites; no global installation."""
import hashlib,json,os,posixpath,shutil,tarfile,time,urllib.request
from pathlib import Path

def need(ok,why):
    if not ok:raise RuntimeError(why)

def sha(path):
    with Path(path).open('rb') as stream:return hashlib.file_digest(stream,'sha256').hexdigest()

def acquire(root,work,budget_receipt=None):
    lock=root/'tools/local-linux-tools.lock.json';data=json.loads(lock.read_bytes());dest=root/'artifacts/linux-tool-inputs';dest.mkdir(parents=True,exist_ok=True);outputs=[];started=time.monotonic()
    class Redirect(urllib.request.HTTPRedirectHandler):
        def redirect_request(self,req,fp,code,msg,headers,newurl):
            from urllib.parse import urlparse
            u=urlparse(newurl);need(u.scheme=='https' and (u.hostname in ('github.com','nodejs.org','release-assets.githubusercontent.com','objects.githubusercontent.com') or u.hostname.endswith('.githubusercontent.com')),'official tool redirect only')
            return super().redirect_request(req,fp,code,msg,headers,newurl)
    opener=urllib.request.build_opener(urllib.request.ProxyHandler({}),Redirect())
    import concurrent.futures,re
    prior=json.loads((Path(budget_receipt)/'receipt.json').read_bytes()) if budget_receipt else None
    need(prior and prior['purpose']=='LOCAL_PRIVATE_TOOL_DATA' and prior['terminal'] is True,'retained original transfer elapsed')
    remaining=480-prior['elapsedSeconds']-10
    deadline=started+remaining
    for name,row in data['tools'].items():
        target=dest/(name+'.tar.gz')
        if target.exists():need(sha(target)==row['sha256'],'retained exact tool input')
        else:
            headers={'User-Agent':'own02-private-tools','Accept-Encoding':'identity'}
            with opener.open(urllib.request.Request(row['url'],headers=headers,method='HEAD'),timeout=10) as response:
                need(response.status==200 and response.headers.get('Accept-Ranges')=='bytes','official bounded range transfer support')
                total=int(response.headers['Content-Length'])
            need(0<total<=row.get('bytes',row.get('maximumRawBytes')) and ('bytes' not in row or total==row['bytes']),'exact official transfer size')
            prefix=target.with_suffix('.part');offset=prefix.stat().st_size if prefix.exists() else 0
            need(0<=offset<total,'retained prefix bounds')
            step=(total-offset+7)//8;parts=[]
            def fetch(index,start,end):
                part=dest/(name+'.range-'+str(index)+'.part');need(not part.exists(),'single resumed transfer; no hidden retry')
                request=urllib.request.Request(row['url'],headers={**headers,'Range':'bytes='+str(start)+'-'+str(end)})
                with opener.open(request,timeout=15) as response,part.open('xb') as output:
                    need(response.status==206 and response.headers.get('Content-Range')=='bytes '+str(start)+'-'+str(end)+'/'+str(total),'exact bounded range response')
                    count=0
                    while chunk:=response.read(262144):
                        count+=len(chunk);need(count<=end-start+1 and time.monotonic()<deadline,'approved cumulative data-transfer bounds');output.write(chunk)
                    need(count==end-start+1,'complete explicit range')
                return part
            with concurrent.futures.ThreadPoolExecutor(max_workers=8) as pool:
                futures=[pool.submit(fetch,i,start,min(start+step,total)-1) for i,start in enumerate(range(offset,total,step))]
                parts=[f.result(timeout=max(.01,deadline-time.monotonic())) for f in futures]
            temporary=dest/(name+'.assembled.part');need(not temporary.exists(),'fresh full-body assembly')
            with temporary.open('xb') as output:
                for part in ([prefix] if offset else [])+parts:
                    with part.open('rb') as source:shutil.copyfileobj(source,output,1048576)
                output.flush();os.fsync(output.fileno())
            need(temporary.stat().st_size==total and sha(temporary)==row['sha256'],'official exact full archive identity after ranged transfer')
            temporary.rename(target)
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
