"""Explicitly authorized private Linux prerequisites; no global installation."""
import hashlib,json,os,posixpath,shutil,tarfile,time,urllib.request
from pathlib import Path

def need(ok,why):
    if not ok:raise RuntimeError(why)

def sha(path):
    with Path(path).open('rb') as stream:return hashlib.file_digest(stream,'sha256').hexdigest()

def acquire(root,work,budget_receipt=None):
    """Approved data-only continuation: original bytes, IPv4, no hidden retry."""
    import concurrent.futures,re,subprocess,uuid
    from urllib.parse import urlparse,urljoin
    lock=root/'tools/local-linux-tools.lock.json';data=json.loads(lock.read_bytes());policy=data['transferException']
    need(policy['explicitHumanConsent'] is True and policy['totalSeconds']==1200,'exact direct human cumulative transfer permission')
    curl=Path(policy['curl']['path']);need(curl.is_file() and sha(curl)==policy['curl']['sha256'],'pinned existing Microsoft Windows curl')
    prior=json.loads((Path(budget_receipt)/'receipt.json').read_bytes());need(prior['purpose']=='LOCAL_PRIVATE_TOOL_DATA' and prior['terminal'] is True,'retained actual transfer')
    transfers=[json.loads(p.read_bytes()) for p in (root/'artifacts/tech-refresh').glob('*/receipt.json')]
    transfers=[p for p in transfers if p.get('purpose')=='LOCAL_PRIVATE_TOOL_DATA'];need(all(p['terminal'] is True for p in transfers),'previous transfers terminal')
    spent=sum(p['elapsedSeconds'] for p in transfers);started=time.monotonic();deadline=started+1200-spent-10
    need(deadline>started,'remaining approved cumulative budget')
    dest=root/'artifacts/linux-tool-inputs';dest.mkdir(parents=True,exist_ok=True);attempt=uuid.uuid4().hex;outputs=[];requests=[]
    env={k:v for k,v in os.environ.items() if k.upper() not in ('CURL_HOME','CURL_CA_BUNDLE','CURL_SSL_BACKEND','SSL_CERT_FILE','SSL_CERT_DIR','HTTP_PROXY','HTTPS_PROXY','ALL_PROXY')}
    def allowed(url):
        x=urlparse(url);need(x.scheme=='https' and (x.hostname in ('nodejs.org','github.com','objects.githubusercontent.com','release-assets.githubusercontent.com') or (x.hostname or '').endswith('.githubusercontent.com')),'official HTTPS host only')
    def request(url,label,extra):
        allowed(url);left=deadline-time.monotonic();need(left>1,'original approved transfer deadline')
        header=dest/(label+'.'+attempt+'.headers');need(not header.exists(),'fresh header record')
        argv=[str(curl),'-q','--ipv4','--silent','--show-error','--fail','--proto','=https','--proxy','','--noproxy','*','--connect-timeout','10','--max-time',str(left),'--dump-header',str(header),*extra,'--write-out','%{http_code}',url]
        result=subprocess.run(argv,capture_output=True,env=env,timeout=left+1)
        need(len(result.stdout)<=1024 and len(result.stderr)<=16384 and header.is_file() and header.stat().st_size<=16384,'bounded curl metadata')
        raw=header.read_bytes();blocks=[b for b in re.split(br'\r?\n\r?\n',raw) if b.startswith(b'HTTP/')];need(blocks,'typed HTTP response')
        lines=blocks[-1].decode('iso-8859-1').splitlines();status=int(lines[0].split()[1]);headers={}
        for line in lines[1:]:
            key,sep,value=line.partition(':');need(sep,'typed header');key=key.strip().lower();need(key not in headers or key not in ('location','content-length','content-range'),'no ambiguous authority/range headers');headers[key]=value.strip()
        requests.append({'label':label,'host':urlparse(url).hostname,'status':status,'curlExit':result.returncode,'headerSha256':sha(header)})
        return result,status,headers
    def resolve(url,name):
        for hop in range(4):
            result,status,headers=request(url,name+'-head'+str(hop),['--head','--output',os.devnull])
            need(result.returncode==0,'official HEAD transport failed; no implicit retry')
            if status in (301,302,303,307,308):url=urljoin(url,headers['location']);allowed(url);continue
            need(status==200 and headers.get('accept-ranges','').lower()=='bytes','official byte range support');return url,int(headers['content-length'])
        raise RuntimeError('official redirect bound')
    for name,row in sorted(data['tools'].items(),key=lambda x:x[0]!='pwsh'):
        target=dest/(name+'.tar.gz')
        if target.exists():need(sha(target)==row['sha256'],'complete retained exact official archive')
        else:
            url,total=resolve(row['url'],name)
            need(0<total<=row.get('bytes',row.get('maximumRawBytes')) and ('bytes' not in row or total==row['bytes']),'exact official byte extent')
            prefix=target.with_suffix('.part');offset=prefix.stat().st_size if prefix.exists() else 0;need(0<=offset<total,'retained prefix extent')
            step=(total-offset+7)//8
            def fetch(index,start,end):
                part=dest/(name+'.range-'+str(index)+'.part');retained=part.stat().st_size if part.exists() else 0;need(0<=retained<=end-start+1,'retained range bound')
                if retained==end-start+1:return part
                begin=start+retained;tail=dest/(name+'.range-'+str(index)+'.'+attempt+'.tail');need(not tail.exists(),'fresh missing-byte destination')
                expected=end-begin+1
                result,status,headers=request(url,name+'-range'+str(index),['--range',str(begin)+'-'+str(end),'--max-filesize',str(expected),'--output',str(tail)])
                need(status==206 and headers.get('content-range')=='bytes '+str(begin)+'-'+str(end)+'/'+str(total),'exact missing range response')
                count=tail.stat().st_size if tail.exists() else 0;need(count<=expected,'range response size')
                if count:
                    with tail.open('rb') as src,part.open('ab' if retained else 'xb') as dst:shutil.copyfileobj(src,dst,1048576);dst.flush();os.fsync(dst.fileno())
                need(result.returncode==0 and count==expected,'curl missing-range transport incomplete; retained only actual received prefix, no retry')
                return part
            with concurrent.futures.ThreadPoolExecutor(max_workers=8) as pool:
                futures=[pool.submit(fetch,i,start,min(start+step,total)-1) for i,start in enumerate(range(offset,total,step))]
                parts=[f.result(timeout=max(.01,deadline-time.monotonic())) for f in futures]
            assembly=dest/(name+'.'+attempt+'.assembled.part');need(not assembly.exists(),'fresh assembly')
            with assembly.open('xb') as output:
                for part in ([prefix] if offset else [])+parts:
                    with part.open('rb') as source:shutil.copyfileobj(source,output,1048576)
                output.flush();os.fsync(output.fileno())
            need(assembly.stat().st_size==total and sha(assembly)==row['sha256'],'official full SHA256 after exact ranged continuation');assembly.rename(target)
        outputs.append({'name':name,'path':str(target),'bytes':target.stat().st_size,'sha256':sha(target)})
    need(time.monotonic()<deadline,'approved original cumulative transfer clock')
    (work/'private-tool-inputs.json').write_bytes((json.dumps({'state':'OFFICIAL_EXACT_PRIVATE_TOOL_ARCHIVES_ACQUIRED_NOT_EXECUTED','sourceLockSHA256':sha(lock),'archives':outputs,'requests':requests,'curlSha256':sha(curl),'previousActiveSeconds':spent,'thisTransferSeconds':time.monotonic()-started,'cumulativeMaximumSeconds':1200,'globalChanges':False,'SDK':0},indent=2)+'\n').encode())

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


def linux_npm_rows(root):
    import base64
    lock=json.loads((root/'OperatorPanel/package-lock.json').read_bytes());rows=[]
    for name,row in lock['packages'].items():
        if not name or not all(not row.get(k) or value in row[k] for k,value in [('os','linux'),('cpu','x64'),('libc','glibc')]):continue
        need(row['integrity'].startswith('sha512-') and row['resolved'].startswith('https://registry.npmjs.org/'),'exact official lock input')
        digest=base64.b64decode(row['integrity'][7:],validate=True).hex();need(len(digest)==128,'SHA512 lock')
        relative=Path('_cacache/content-v2/sha512')/digest[:2]/digest[2:4]/digest[4:]
        rows.append((name,row,digest,relative))
    need(len(rows)==23,'complete Linux x64 glibc frontend closure');return rows

def verify_npm_blob(path,digest):
    need(path.is_file() and not path.is_symlink() and 0<path.stat().st_size<=67108864,'bounded regular npm original')
    with path.open('rb') as stream:need(hashlib.file_digest(stream,'sha512').hexdigest()==digest,'exact lock SRI')

def acquire_npm(root,work):
    import concurrent.futures,subprocess,uuid
    from urllib.parse import urlparse
    curl=json.loads((root/'tools/local-linux-tools.lock.json').read_bytes())['transferException']['curl'];need(sha(curl['path'])==curl['sha256'],'pinned curl')
    cache=root/'artifacts/private-npm-cache';rows=linux_npm_rows(root);started=time.monotonic();deadline=started+150
    env={k:v for k,v in os.environ.items() if k.upper() not in ('CURL_HOME','CURL_CA_BUNDLE','CURL_SSL_BACKEND','SSL_CERT_FILE','SSL_CERT_DIR','HTTP_PROXY','HTTPS_PROXY','ALL_PROXY')}
    def one(item):
        name,row,digest,relative=item;target=cache/relative
        if not target.exists():
            url=urlparse(row['resolved']);need(url.scheme=='https' and url.hostname=='registry.npmjs.org' and not url.username and not url.fragment,'official exact registry URL')
            target.parent.mkdir(parents=True,exist_ok=True);part=target.with_name(target.name+'.'+uuid.uuid4().hex+'.part');left=deadline-time.monotonic();need(left>1,'frontend data clock')
            p=subprocess.run([curl['path'],'-q','--ipv4','--silent','--show-error','--fail','--proto','=https','--proxy','','--noproxy','*','--connect-timeout','10','--max-time',str(left),'--max-filesize','67108864','--output',str(part),row['resolved']],env=env,capture_output=True,timeout=left+1)
            need(p.returncode==0 and len(p.stderr)<16384,'exact registry download failed, no implicit retry');verify_npm_blob(part,digest);part.rename(target)
        verify_npm_blob(target,digest);return {'name':name,'sha512':digest,'bytes':target.stat().st_size}
    with concurrent.futures.ThreadPoolExecutor(max_workers=3) as pool:proof=list(pool.map(one,rows))
    need(time.monotonic()<deadline,'frontend data deadline')
    (work/'linux-npm-inputs.json').write_bytes((json.dumps({'state':'EXACT_LOCKED_LINUX_NPM_RAW_INPUTS_NOT_EXECUTED','packages':proof,'lockSha256':sha(root/'OperatorPanel/package-lock.json'),'globalChanges':False},indent=2)+'\n').encode())

def copy_npm(root,source):
    dest=root/'artifacts/private-npm-cache';proof=[]
    for name,row,digest,relative in linux_npm_rows(root):
        original=source/relative;verify_npm_blob(original,digest);target=dest/relative
        if not target.exists():
            target.parent.mkdir(parents=True,exist_ok=True)
            with original.open('rb') as a,target.open('xb') as b:shutil.copyfileobj(a,b,1048576)
        verify_npm_blob(target,digest);proof.append({'name':name,'sha512':digest,'bytes':target.stat().st_size})
    return proof
