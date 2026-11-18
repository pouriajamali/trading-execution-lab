"""Own local SDK11 stages. Existing bounded launcher only; no CI impersonation."""
import ast, ctypes, hashlib, importlib.util, json, os, struct, subprocess, sys
from pathlib import Path
ROOT=Path(__file__).resolve().parents[1]

def need(ok,why):
    if not ok: raise RuntimeError(why)

def digest(path,kind='sha256'):
    with Path(path).open('rb') as stream:return hashlib.file_digest(stream,kind).hexdigest()

def module(name,path):
    spec=importlib.util.spec_from_file_location(name,path);obj=importlib.util.module_from_spec(spec)
    sys.modules[name]=obj;spec.loader.exec_module(obj);return obj

def write(path,value):
    raw=(json.dumps(value,indent=2)+'\n').encode();need(len(raw)<=1048576,'local receipt bound')
    with Path(path).open('xb') as stream:stream.write(raw);stream.flush();os.fsync(stream.fileno())

def current_inputs(b,work,phase):
    """Current own containment and exact existing data; no borrowed host fact."""
    tools=ROOT/'tools';guard=module('qualification_input_guard',tools/'qualification_input_guard.py')
    catalog=json.loads((tools/'sdk11-normal-inputs.lock.json').read_bytes())['rids'][b['rid']]['input']
    need(catalog['sdk']=='11.0.100' and catalog['runtime']=='11.0.0','fixed local toolchain')
    sdk=Path(b['sdkRoot']);archive=Path(b['sdkArchive'])
    if os.name=='nt':
        k=ctypes.WinDLL('kernel32',use_last_error=True);buf=ctypes.create_string_buffer(144)
        k.QueryInformationJobObject.argtypes=[ctypes.c_void_p,ctypes.c_int,ctypes.c_void_p,ctypes.c_ulong,ctypes.c_void_p]
        need(k.QueryInformationJobObject(None,9,buf,144,None),'current own Job query')
        flags=struct.unpack_from('<I',buf,16)[0];tasks=struct.unpack_from('<I',buf,40)[0]
        affinity=struct.unpack_from('<Q',buf,48)[0];process_memory,job_memory=struct.unpack_from('<QQ',buf,112)
        need(flags==0x2318 and tasks==64 and process_memory==job_memory==4294967296 and 0<affinity.bit_count()<=2,'current own Job caps')
        native=module('own_local_windows_input',tools/'normal_windows_input.py')
        common=module('own_local_shared_data',tools/'check_dotnet11.py')
        cpu_root=work/'cpu';cpu_root.mkdir();cpu=native.measure_cpu(common,cpu_root)
        caps={'flags':flags,'tasks':tasks,'memoryBytes':job_memory,'affinity':affinity,'cpu':cpu}
    else:
        group=Path('/proc/self/cgroup').read_text().strip();need(group=='0::'+b['cgroup'] and os.getuid()==1000,'current own Linux group')
        cg=Path('/sys/fs/cgroup'+b['cgroup']);caps={x:(cg/x).read_text().strip() for x in ('memory.max','memory.swap.max','pids.max','cpu.max')}
        need(caps=={'memory.max':'4294967296','memory.swap.max':'0','pids.max':'64','cpu.max':'200000 100000'},'current own Linux caps')
        flags=[set(x.split(':',1)[1].split()) for x in Path('/proc/cpuinfo').read_text().splitlines() if x.startswith('flags')]
        need(flags and all({'cx16','popcnt','pni','ssse3','sse4_1','sse4_2','lahf_lm'}<=x for x in flags),'current x86-64-v2')
    if phase=='probe':
        need(archive.is_file() and archive.stat().st_size==catalog['bytes'] and digest(archive,'sha512')==catalog['sha512'],'existing exact SDK archive')
        if os.name!='nt':
            if b.get('reuseExistingSDKData'):
                policy=json.loads((tools/'sdk11-own-linux-resume-20261118.json').read_bytes())
                need(str(sdk)==policy['existingSDKRoot'] and digest(tools/'sdk11-existing-linux-data-candidate.json')==policy['existingSDKDataHandoffSHA256'],'identity-bound existing SDK data candidate only')
                need(sdk.is_dir(),'existing SDK data present; current full verification still mandatory')
            else:
                need(not sdk.exists(),'fresh local Linux SDK allocation; old partials untouched')
                copy=module('own_local_linux_copy',tools/'materialize_qualification_linux.py');copy.materialize(catalog,archive,sdk)
    print(json.dumps({'ownStage':'SDK_FULL_DATA_VERIFY','rid':b['rid'],'root':str(sdk)}),flush=True)
    guard.verify_tree(sdk,catalog['members'],b['rid'],full=True)
    print(json.dumps({'ownStage':'SDK_FULL_DATA_VERIFIED','members':len(catalog['members'])}),flush=True)
    if os.name!='nt' and b.get('privateLinuxToolInputs'):
        helper=module('own_private_linux_tools',ROOT/'scripts/prepare_local_linux_tools.py')
        if phase=='probe' or b.get('materializePrivateLinuxTools') is True:
            helper.materialize(ROOT,input_path(b['privateLinuxToolInputs']),guard)
            copied=helper.copy_npm(ROOT,input_path(b['privateLinuxToolInputs']).parent/'private-npm-cache')
            write(work/'linux-npm-cache-inputs.json',{'packages':copied,'lockSha256':digest(ROOT/'OperatorPanel/package-lock.json')})
        else:helper.verify(ROOT)
    write(work/'current-local-inputs.json',{'rid':b['rid'],'catalogSha256':digest(tools/'sdk11-normal-inputs.lock.json'),'memberManifestSha256':catalog['memberManifestSha256'],'caps':caps,'SDKRoot':str(sdk),'producerHostFactBorrowed':False,'SDKExecutions':0})
    if phase!='probe':
        q=Path(b['localQualification']);proof=json.loads(q.read_bytes());terminal=json.loads(q.with_name('receipt.json').read_bytes())
        need(digest(q)==b['localQualificationSha256'] and proof['state']=='OWN_LOCAL_SDK11_RUNTIME_OBSERVED'
             and proof['rid']==b['rid'] and proof['SDKRoot']==str(sdk)
             and proof['catalogSha256']==digest(tools/'sdk11-normal-inputs.lock.json')
             and terminal['status']=='COMPLETED' and terminal['terminal'] is True,'actual terminal own local qualification required')
    for key in list(os.environ):
        if key.upper().startswith(('COREHOST_','LD_')):del os.environ[key]
    os.environ.update(DOTNET_ROOT=str(sdk),DOTNET_ROOT_X64=str(sdk),DOTNET_HOST_PATH=b['dotnet'],DOTNET_MULTILEVEL_LOOKUP='0',DOTNET_EnableDiagnostics='0',DOTNET_NOLOGO='1',DOTNET_CLI_UI_LANGUAGE='en-US',DOTNET_CLI_WORKLOAD_UPDATE_NOTIFY_DISABLE='true',MSBUILDDISABLENODEREUSE='1',DOTNET_CLI_USE_MSBUILD_SERVER='0',DOTNET_CLI_DO_NOT_USE_MSBUILD_SERVER='1')
    if os.name=='nt':
        for key in list(os.environ):
            if key.upper() in ('PROGRAMFILES','PROGRAMFILES(X86)','PROGRAMW6432'):del os.environ[key]
        for key,folder in [('PROGRAMFILES','programfiles'),('PROGRAMFILES(X86)','programfiles-x86'),('PROGRAMW6432','programfiles')]:
            p=ROOT/'artifacts/private-discovery'/folder;p.mkdir(parents=True,exist_ok=True);need(not any(p.iterdir()),'private empty Windows discovery root');os.environ[key]=str(p)

def qualify(b,work):
    """First actual SDK/native runtime validation on this specific local host."""
    sdk=Path(b['sdkRoot']);p=work/'native-probe';p.mkdir();feed=p/'empty-feed';feed.mkdir()
    (p/'NuGet.Config').write_bytes(('<?xml version="1.0"?><configuration><packageSources><clear/><add key="empty-local" value="'+str(feed)+'"/></packageSources><fallbackPackageFolders><clear/></fallbackPackageFolders></configuration>').encode())
    (p/'Probe.csproj').write_bytes(b'<Project Sdk="Microsoft.NET.Sdk"><PropertyGroup><OutputType>Exe</OutputType><TargetFramework>net11.0</TargetFramework><RuntimeFrameworkVersion>11.0.0</RuntimeFrameworkVersion><UseAppHost>false</UseAppHost><LangVersion>15.0</LangVersion><EnableRuntimePackDownload>false</EnableRuntimePackDownload><DisableTransitiveFrameworkReferenceDownloads>true</DisableTransitiveFrameworkReferenceDownloads></PropertyGroup></Project>')
    (p/'Program.cs').write_bytes(b'using System;using System.Diagnostics;using System.Runtime.InteropServices;using System.Text.Json;class Program{static void Main(){if(Environment.Version!=new Version(11,0,0)||RuntimeInformation.ProcessArchitecture!=Architecture.X64)throw new Exception("runtime or architecture");string? core=null;foreach(ProcessModule m in Process.GetCurrentProcess().Modules)if(m.ModuleName=="coreclr.dll"||m.ModuleName=="libcoreclr.so")core=m.FileName;if(core==null)throw new Exception("actual loaded coreclr");Console.WriteLine(JsonSerializer.Serialize(new {runtime=Environment.Version.ToString(),framework=RuntimeInformation.FrameworkDescription,os=RuntimeInformation.OSDescription,architecture=RuntimeInformation.ProcessArchitecture.ToString(),coreclr=core}));}}')
    commands=[['--version'],['--info'],['--list-sdks'],['--list-runtimes'],['restore',str(p/'Probe.csproj'),'--configfile',str(p/'NuGet.Config'),'-p:NuGetAudit=false','-p:UseSharedCompilation=false'],['build',str(p/'Probe.csproj'),'-c','Release','--no-restore','-p:UseSharedCompilation=false'],[str(p/'bin/Release/net11.0/Probe.dll')]]
    results=[]
    retained=b.get('retainedQualificationMetadata')
    if retained:
        previous=Path(retained['directory']);terminal=json.loads((previous/'receipt.json').read_bytes());inputs=json.loads((previous/'current-local-inputs.json').read_bytes())
        need(digest(previous/'receipt.json')==retained['receiptSha256'] and terminal['terminal'] is True
             and terminal['bindingSha256']==retained['bindingSha256'] and inputs['catalogSha256']==digest(ROOT/'tools/sdk11-normal-inputs.lock.json')
             and inputs['SDKRoot']==str(sdk) and b'actual local SDK qualification command 4 failed' in (previous/'phase.log').read_bytes(), 'retained exact incomplete probe cause')
        need((previous/'sdk-0.log').read_text().strip()=='11.0.100','retained actual SDK metadata')
        results=[{'argv':commands[i],'retainedLogSha256':digest(previous/('sdk-'+str(i)+'.log')),'source':'Exact prior guarded execution reached failure at command4; metadata0..3 are reused, not rerun'} for i in range(4)]
    executed=0
    for index,args in enumerate(commands):
        if retained and index<4:continue
        if index in (4,5):args=[*args,'-p:ImportDirectoryBuildProps=false','-p:ImportDirectoryBuildTargets=false']
        result=subprocess.run([b['dotnet'],*args],cwd=p,capture_output=True,timeout=20)
        need(len(result.stdout)+len(result.stderr)<=1048576,'qualification log bound')
        (work/('sdk-'+str(index)+'.log')).write_bytes(result.stdout+result.stderr)
        need(result.returncode==0,'actual local SDK qualification command '+str(index)+' failed')
        row={'argv':args,'exit':0,'stdoutSha256':hashlib.sha256(result.stdout).hexdigest()};results.append(row);write(work/('sdk-'+str(index)+'.json'),row);executed+=1
        if index==0:need(result.stdout.decode().strip()=='11.0.100','actual selected SDK11')
        if index==6:runtime=json.loads(result.stdout.decode().strip())
    core=Path(runtime['coreclr']).resolve();expected=(sdk/'shared/Microsoft.NETCore.App/11.0.0'/('coreclr.dll' if os.name=='nt' else 'libcoreclr.so')).resolve()
    need(core==expected,'actual local loaded private CoreCLR')
    write(work/'host-qualification.json',{'state':'OWN_LOCAL_SDK11_RUNTIME_OBSERVED','rid':b['rid'],'SDKRoot':str(sdk),'catalogSha256':digest(ROOT/'tools/sdk11-normal-inputs.lock.json'),'runtime':runtime,'coreclrSha256':digest(core),'sourceCommit':b['sourceCommit'],'commands':results,'SDKCommands':executed,'retainedMetadataCommands':4 if retained else 0,'vendorSupport':'UNCONFIRMED_EXPERIMENTAL_WINDOWS_WITH_EXPLICIT_HUMAN_CONSENT' if os.name=='nt' else 'Ubuntu24.04_LocalWSL2_ActualExt4AndCgroup','scope':'Current own local native runtime observation; not producer admission, actual product tests, CI or global SDK_READY'})

def input_path(value):
    if os.name!='nt' and len(value)>2 and value[1]==':':
        return Path('/mnt/'+value[0].lower()+'/'+value[3:].replace('\\','/'))
    return Path(value)

def dependency_source():
    return {str(p.relative_to(ROOT)):digest(p) for p in [ROOT/'Directory.Build.props',ROOT/'global.json',*(ROOT/x/(x+'.csproj') for x in ('ExecutionLab','ExecutionLab.Hosting','ExecutionLab.Persistence','ExecutionLab.Api','ExecutionLab.Tests','ExecutionLab.Measurements'))]}

def curate(b,work):
    """Actual finite14 factory, fully quarantined originals, current official trust.

    Earlier03 signatures are retained; their explicitly UNKNOWN current-PKI
    scope requires this new local online validation before our first restore.
    No prior success is relabeled as independent CRL verification.
    """
    import shutil,time,threading,http.server
    started=time.monotonic();factory=module('own_input14_factory',ROOT/'scripts/input02_sdk14_delta.py')
    handoff=input_path(b['ordinaryHandoff']);need(digest(handoff)==b['ordinaryHandoffSha256'],'exact producer ordinary data handoff')
    pin=json.loads((ROOT/'tools/sdk11-own-input-candidate.json').read_bytes());need(digest(handoff)==pin['producerDataSha256'],'source-pinned producer identity')
    data=json.loads(handoff.read_bytes());rows=data['ordinary02CandidatePackages'];need(len(rows)==33 and len({(x['id'].casefold(),x['version']) for x in rows})==33,'finite actual candidate originals')
    fresh_ref=json.loads((ROOT/'tools/sdk11-own-current-advisory.json').read_bytes()) if (ROOT/'tools/sdk11-own-current-advisory.json').exists() else None
    pages=[]
    if fresh_ref:
        import gzip
        fp=input_path(fresh_ref['path']);need(digest(fp)==fresh_ref['sha256'],'current additive producer advisory identity')
        fresh=json.loads(fp.read_bytes());snapshot=fresh['completeAdvisory']
        need(fresh['consumerProjectId']=='02' and fresh['oldImmutableHandoff']['sha256']==b['ordinaryHandoffSha256']
             and fresh['consumerSourcePin']['sha256']==digest(ROOT/'tools/sdk11-own-input-candidate.json'),'same immutable exact candidate set')
        need({(x['id'].casefold(),x['version']) for x in snapshot['exactSelectedPackages']}=={(x['id'].casefold(),x['version']) for x in rows},'fresh advisory exact33 identities')
        responses=snapshot['responses'];need(len(responses)==4,'all service/index/base/update observations')
        decoded=[]
        for item in responses:
            bodies=[]
            for key in ('rawBody','decodedBody'):
                proof=item[key];path=input_path(proof['path']);raw=path.read_bytes();need(len(raw)==proof['bytes'] and hashlib.sha256(raw).hexdigest()==proof['sha256'],'actual complete advisory bytes');bodies.append(raw)
            need(item['encoding']=='gzip' and gzip.decompress(bodies[0])==bodies[1],'wire/decoded identity')
            decoded.append(bodies[1])
        index=json.loads(decoded[1]);need(len(index)==2 and [x['@id'] for x in index]==[x['url'] for x in responses[2:]],'all declared fresh snapshot pages')
        pages=decoded[2:];advisory={'source':fresh_ref,'observedAtUnix':fresh['observedAtUnix'],'maxAgeSeconds':fresh['maxAgeSeconds'],'scope':'Additive current advisory only; no legacy PKI or host fact renewed'}
    else:
        advisory=data['advisoryReuse'];old=input_path(b['testInputHandoff']);need(digest(old)==b['testInputHandoffSha256'],'retained advisory identity');snapshot=json.loads(old.read_bytes())['advisory'];need(snapshot['observedAtUnix']==advisory['observedAtUnix'] and len(snapshot['pages'])==2,'same complete advisory snapshot')
        for item in snapshot['pages']:
            path=input_path(item['actualBytePath']);raw=path.read_bytes();need(len(raw)==item['bytes'] and hashlib.sha256(raw).hexdigest()==item['actualDecodedBodySHA256'],'actual complete advisory bytes');pages.append(raw)
    need(0<=time.time()-advisory['observedAtUnix']<=advisory['maxAgeSeconds']==86400,'current applicable advisory horizon')
    refresh=b.get('refreshApplicableAudit') is True
    retained=None
    if refresh:
        admission=ROOT/'artifacts/tech-refresh/audit-admission.json';old_bytes=admission.read_bytes();retained=json.loads(old_bytes)
        need(retained['sdkBinding']==b['sdkIdentity'] and retained['dependencySource']==dependency_source(),'same own qualified SDK and dependency source')
        for name,expected_hash in {**retained['locks'],**retained['assets']}.items():need(digest(ROOT/name)==expected_hash,'retained exact six locks/assets before audit-only refresh')
        previous=Path(retained['curationReceipt']);completed=json.loads(previous.read_bytes());terminal=json.loads(previous.with_name('receipt.json').read_bytes())
        need(completed['state']=='ACTUAL_LOCAL_SDK14_GRAPH_LOCK_ASSET_AUDIT_COMPLETED' and completed['SDKCommands']==14 and terminal['status']=='COMPLETED' and terminal['terminal'] is True,'actual completed own original14 retained, no failed result promotion')
        need(digest(retained['audit'])==retained['auditSha256'],'retained actual applicable audit identity')
        write(work/'retained-audit-admission.json',retained)
        feed=work/'raw';feed.mkdir()
    else:
        feed=work/'raw';feed.mkdir()
    cache=ROOT/'artifacts/private-nuget';cache.mkdir(parents=True,exist_ok=True)
    need(any(cache.iterdir()) if refresh else not any(cache.iterdir()),'reuse only admitted own retained cache; first curation remains cold')
    raw_paths=[];expected=[]
    for row in rows:
        source=input_path(row['rawArchive']['path']);rawrow=row['rawArchive'];target=feed/(row['id'].lower()+'.'+row['version']+'.nupkg')
        h=hashlib.sha256();h512=hashlib.sha512();size=0
        if refresh:
            original=Path(retained['localFeed'])/target.name
            need(original.is_file() and not original.is_symlink() and original.stat().st_size==rawrow['bytes'],'same retained original extent')
            with original.open('rb') as src,target.open('xb') as dst:
                while chunk:=src.read(1048576):size+=len(chunk);h.update(chunk);h512.update(chunk);dst.write(chunk)
                dst.flush();os.fsync(dst.fileno())
            need(digest(source)==rawrow['sha256'],'same source-pinned producer original')
        else:
            with source.open('rb') as src,target.open('xb') as dst:
                while chunk:=src.read(1048576):
                    size+=len(chunk);need(size<=rawrow['bytes'],'original byte bound while copying');h.update(chunk);h512.update(chunk);dst.write(chunk)
                dst.flush();os.fsync(dst.fileno())
        need(size==rawrow['bytes'] and h.hexdigest()==rawrow['sha256'] and h512.hexdigest()==rawrow['sha512'],'exact quarantined original copied')
        for proof in [row['memberManifest'],*row['originalData']]:
            path=input_path(proof['path']);need(path.is_file() and path.stat().st_size==proof['bytes'] and digest(path)==proof['sha256'],'retained member/CMS/notices identity')
        raw_paths.append(target);item={'id':row['id'],'version':row['version'],'sha256':rawrow['sha256']}
        value=row['normalizedNuGetContentHash']
        if value!='UNKNOWN':item['expectedNormalizedContentHash']=value
        expected.append(item)
    bodies={};calls=[]
    class Handler(http.server.BaseHTTPRequestHandler):
        def do_GET(self):
            need(len(calls)<128 and len(self.path)<=512,'finite snapshot request bound');calls.append(self.path);body=bodies.get(self.path)
            self.send_response(200 if body is not None else 404);self.send_header('Content-Type','application/json');self.send_header('Content-Length',str(len(body or b'')));self.send_header('Cache-Control','no-store');self.end_headers()
            if body is not None:self.wfile.write(body)
        def log_message(self,*args):pass
    server=http.server.ThreadingHTTPServer(('127.0.0.1',0),Handler);base='http://127.0.0.1:'+str(server.server_port)
    bodies['/v3/index.json']=json.dumps({'version':'3.0.0','resources':[{'@id':base+'/vuln/index.json','@type':'VulnerabilityInfo/6.7.0'}]}).encode()
    bodies['/vuln/index.json']=json.dumps([{**item,'@id':base+'/vuln/'+str(i)+'.json'} for i,item in enumerate(index)] if fresh_ref else [{'@name':'base' if i==0 else 'updates','@id':base+'/vuln/'+str(i)+'.json','@updated':'2026-11-16T23:30:08Z'} for i in range(2)]).encode()
    for i,raw in enumerate(pages):bodies['/vuln/'+str(i)+'.json']=raw
    thread=threading.Thread(target=server.serve_forever,daemon=True);thread.start();graphs=work/'graphs';graphs.mkdir()
    plan=factory.command_plan(b['dotnet'],ROOT,work,raw_paths);config=Path(plan['configPath']);config.write_bytes(factory.config_bytes(feed,cache,server.server_port,sorted(factory.OFFICIAL_REPOSITORY_CERTIFICATES)))
    os.environ['NUGET_CERT_REVOCATION_MODE']='online';os.environ['NUGET_PACKAGES']=str(cache)
    locks=[ROOT/x/'packages.lock.json' for x in factory.PROJECTS]
    locked=os.name!='nt' or refresh
    baseline={str(p.relative_to(ROOT)):digest(p) for p in locks} if locked else None
    need(all(p.exists() for p in locks) if locked else not any(p.exists() for p in locks),'signed existing locks on Linux; no Windows lock overwrite')
    normalized={};executed=[]
    if refresh:
        old_dir=Path(retained['curationReceipt']).parent
        need(digest(old_dir/'curation-6.stdout.log')==completed['commands'][6]['stdoutSha256'] and digest(old_dir/'curation-6.stderr.log')==completed['commands'][6]['stderrSha256'],'exact originally executed own signature report bytes')
        verified=factory.verification_report((old_dir/'curation-6.stdout.log').read_bytes(),(old_dir/'curation-6.stderr.log').read_bytes(),expected,0)
        normalized={(x['id'].casefold(),x['version']):x['normalizedNuGetContentHash'] for x in verified}
        need(len(normalized)==len(rows),'all exact original signature/hash results retained; no new PKI claim')
    try:
        for index,vector in enumerate(plan['commands']):
            if refresh and index<13:continue
            need(time.monotonic()-started<300-5,'original curation active deadline')
            if index==7:need(len(normalized)==len(rows),'all enumerated signature/hash/current-online-trust guards before first restore')
            argv=vector['argv']
            if locked and 7<=index<=12:argv=['--locked-mode' if x=='--use-lock-file' else x for x in argv]
            if index==13:argv=[*argv,'--config',str(config)]
            result=subprocess.run(argv,cwd=ROOT,capture_output=True,timeout=min(vector['maximumSeconds'],300-5-(time.monotonic()-started)))
            need(len(result.stdout)+len(result.stderr)<=1048576,'curation command output bound')
            (work/('curation-'+str(index)+'.stdout.log')).write_bytes(result.stdout);(work/('curation-'+str(index)+'.stderr.log')).write_bytes(result.stderr)
            need(result.returncode==0,'curation command '+str(index)+' failed; retained logs, no retry or product target')
            executed.append({'id':vector['id'],'exit':0,'stdoutSha256':hashlib.sha256(result.stdout).hexdigest(),'stderrSha256':hashlib.sha256(result.stderr).hexdigest()})
            if index==6:
                verified=factory.verification_report(result.stdout,result.stderr,expected,0)
                normalized={(x['id'].casefold(),x['version']):x['normalizedNuGetContentHash'] for x in verified}
                write(work/'official-online-verification.json',{'packages':verified,'newRequiredScope':'Current own local online chain/revocation/timestamp policy; legacy independent UNKNOWN is not relabeled','revocationMode':'online','legacy03NormalizedHashesCompared':17})
        report=json.loads(result.stdout);need(report.get('projects'),'actual applicable audit project coverage')
        def clean(v):
            return all(not(k in ('vulnerabilities','errors','problems','warnings') and x) and clean(x) for k,x in v.items()) if isinstance(v,dict) else all(clean(x) for x in v) if isinstance(v,list) else True
        need(clean(report) and report.get('sources') and all(s in (str(feed),base+'/v3/index.json') for s in report['sources']) and all('/vuln/'+str(i)+'.json' in calls for i in range(2)),'applicable exact-snapshot audit no issues or unapproved sources')
        need(not locked or baseline=={str(p.relative_to(ROOT)):digest(p) for p in locks},'Linux locked restore cannot mutate signed locks')
        selected={};targets={}
        for project,path in zip(factory.PROJECTS,locks):
            lock=json.loads(path.read_bytes());keys=set(lock['dependencies']);need({'net11.0','net11.0/win-x64','net11.0/linux-x64'}<=keys,'actual two-RID lock targets')
            targets[project]=sorted(keys)
            for entries in lock['dependencies'].values():
                for identity,entry in entries.items():
                    if entry['type']=='Project':continue
                    need(entry['type'] in ('Direct','Transitive'),'known lock node type')
                    key=(identity.casefold(),entry['resolved']);need(key in normalized and entry['contentHash']==normalized[key],'actual resolved lock closure equals official normalized bytes')
                    selected[key]=entry['contentHash']
        need(0<=time.time()-advisory['observedAtUnix']<=86400 and time.monotonic()-started<=300,'curation original time/freshness bounds')
        write(work/'curation-admission.json',{'state':'ACTUAL_CURRENT_AUDIT_REFRESH_REUSING_EXACT_COMPLETED_SDK14' if refresh else 'ACTUAL_LOCAL_SDK14_GRAPH_LOCK_ASSET_AUDIT_COMPLETED','retainedOriginalSDK14':{'path':retained['curationReceipt'],'sha256':digest(retained['curationReceipt'])} if refresh else None,'commands':executed,'SDKCommands':len(executed),'selected':[{ 'id':k[0],'version':k[1],'contentHash':v} for k,v in sorted(selected.items())],'targets':targets,'candidateCount':len(rows),'selectedCount':len(selected),'extraCandidateNodesQuarantined':len(rows)-len(selected),'advisorySource':advisory,'snapshotRequests':calls,'seconds':time.monotonic()-started,'inputGuardMethod':'Exact retained original/member/normalized/own prior online report and six unchanged locks/assets; one actual fresh applicable audit, no new PKI validation claim' if refresh else 'exact original/member/CMS/notices data plus own official NuGet all+online strict report, then all actual locks/assets/current audit; no independent PKI claim borrowed'})
        audit=work/'curation-13.stdout.log'
        admission_value={'advisorySource':advisory,'sdkBinding':b['sdkIdentity'],'sdkCatalogSha256':digest(ROOT/'tools/sdk11-normal-inputs.lock.json'),'dependencySource':dependency_source(),'audit':str(audit),'auditSha256':digest(audit),'locks':{str(p.relative_to(ROOT)):digest(p) for p in locks},'assets':{str((ROOT/x/'obj/project.assets.json').relative_to(ROOT)):digest(ROOT/x/'obj/project.assets.json') for x in factory.PROJECTS},'localFeed':str(feed),'config':str(config),'curationReceipt':str(work/'curation-admission.json')}
        target=ROOT/'artifacts/tech-refresh/audit-admission.json'
        if refresh:
            need(target.read_bytes()==old_bytes,'own audit admission changed concurrently')
            temporary=work/'new-audit-admission.json';write(temporary,admission_value);os.replace(temporary,target)
        else:write(target,admission_value)
    finally:
        server.shutdown();server.server_close();thread.join(timeout=2)


def audit_is_current():
    import time
    admission=json.loads((ROOT/'artifacts/tech-refresh/audit-admission.json').read_bytes())
    snapshot=admission.get('advisorySource') or json.loads(Path(admission['curationReceipt']).read_bytes())['advisorySource']
    return 0<=time.time()-snapshot['observedAtUnix']<=snapshot['maxAgeSeconds']==86400
