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
            need(not sdk.exists(),'fresh local Linux SDK allocation; old partials untouched')
            copy=module('own_local_linux_copy',tools/'materialize_qualification_linux.py');copy.materialize(catalog,archive,sdk)
    guard.verify_tree(sdk,catalog['members'],b['rid'],full=True)
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

def curate(b,work):
    raise RuntimeError('Actual producer04 identity-bound ordinary raw/PKI/data handoff required before local curation; no implicit restore or fabricated locks')
