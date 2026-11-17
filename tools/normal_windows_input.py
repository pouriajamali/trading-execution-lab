"""Windows branch of the one shared normal-input API. Import performs no OS work.
Producer history is immutable; every call proves its own source, Job and clock.
"""
from __future__ import annotations
import contextlib,ctypes,hashlib,json,math,os,platform,re,shutil,stat,subprocess,sys,threading,time
from pathlib import Path
FACT='ec8e9b405ca74bd7bbc748575265de2555056d84ff5780a8979bbb01cbd27c48'
ACCEPT='9713a70f809ac7f50a1c73650fc6d3390bccda109e7a2d15c9be581ff91dc8f6'
MANIFEST='7eb452d5eaa748773eb0b12d1abc8da1a9f1c192b06444dc88c6511de56b63c3'
HOST='GitHubHostedWindowsServer2025x64'
PRODUCER='86dcda2c2eb314e4ddc146a992256638fd63c825'
TREE='d796a0d63d098b78686b7da73cf4841659f60489'

def documents(C):
 p=C.HERE/'sdk11-normal-inputs.lock.json';C.need(C.digest(p)==C.PINS['catalogSha256'],'NORMAL_CATALOG_SOURCE_BYTES');cat=C._read(p)
 C.need(cat.get('schema')=='sdk11-shared-normal-input-catalog/v1' and cat.get('state')=='SOURCE_HELD_NORMAL_ACCEPTED_RIDS_ONLY' and cat.get('SDK_READY') is False and cat.get('contractSha256')=='e092c4e8911c2b25f70fda3608d2c04212d3d81f6aaa1214688eea236cfbb089','NORMAL_CATALOG_CONTRACT')
 C.need(cat.get('windowsAdmissionAmendmentSha256')==C.PINS['windowsAdmissionAmendmentSha256'] and C.digest(C.HERE/'sdk11-normal-windows-admission.json')==C.PINS['windowsAdmissionAmendmentSha256'],'NORMAL_WINDOWS_AMENDMENT_IDENTITY')
 e=cat['rids'].get('win-x64');C.need(type(e) is dict and e.get('state')=='ACCEPTED_PRODUCER_FACT_FOR_OWN_ADMITTED_HOST' and e.get('factSha256')==FACT and e.get('acceptanceSha256')==ACCEPT,'NORMAL_WINDOWS_FACT_AUTHORITY')
 fp=C.HERE/'sdk11-normal/accepted-windows-fact.json';ap=C.HERE/'sdk11-normal/accepted-windows-acceptance.json';sp=C.HERE/'dotnet11-host-qualification.schema.json'
 C.need(C.digest(fp)==FACT and C.digest(ap)==ACCEPT and C.digest(sp)==C.PINS['schemaSha256']=='63e04fa5d270c87b93e6e1f4c38bfbcf336b950b39fe1854dc4e514f0661f14c','NORMAL_WINDOWS_FACT_BYTES')
 fact=C._read(fp);accept=C._read(ap);schema=C._read(sp);F=C._load('sdk11_ci_facts',C.PINS['windowsFactHelperSha256']);F.validate_fact(fact,schema)
 validate_catalog(C,e,fact,accept);return e['input'],fact,schema

def validate_catalog(C,e,fact,accept):
 q=fact['qualifiedOn'];c=e.get('input');C.need(q['rid']=='win-x64' and q['hostClass']==HOST and q['runId']=='44083510897' and fact['source']['commit']==e.get('producerCommit')==PRODUCER and fact['source']['tree']==e.get('producerTree')==TREE,'NORMAL_WINDOWS_PRODUCER_HISTORY')
 C.need(accept.get('runId')==44083510897 and any(x.get('id')==134039871625 and x.get('status')=='completed' and x.get('conclusion')=='success' for x in accept.get('jobs',[])),'NORMAL_WINDOWS_PRODUCER_ACCEPTANCE')
 C.need(type(c) is dict and c.get('state')=='ACCEPTED_HOST_TYPED_NORMAL_INPUT' and c.get('normalTransportUse')=='OWN_CURRENT_TYPED_ADMISSION_REQUIRED' and c.get('rid')=='win-x64' and c.get('sdk')=='11.0.100' and c.get('runtime')=='11.0.0','NORMAL_WINDOWS_INPUT_STATE')
 C.need((c.get('url'),c.get('bytes'),c.get('sha512'))==(C.INPUTS['win-x64']['url'],337835326,C.INPUTS['win-x64']['sha512']),'NORMAL_WINDOWS_RAW_IDENTITY')
 C.need(c.get('memberManifestSha256')==fact['tree']['memberManifestSha256']==MANIFEST and hashlib.sha256(C.canonical(c.get('members'))).hexdigest()==MANIFEST and len(c['members'])==5480,'NORMAL_WINDOWS_MEMBER_IDENTITY')

class OwnJob:
 """Query only existing own Job; retain handles and enforce the original clock.
 No limit/policy setter, new Job, credential, or SDK launch is used here.
 """
 def __init__(self,C,ctx,caps,end):
  from ctypes import wintypes as W
  self.C=C;self.ctx=ctx;self.end=end;self.job=self.parent=self.cancel=None;self.thread=None
  C.need(os.name=='nt' and sys.maxsize>2**32,'NORMAL_WINDOWS_CURRENT_HOST');self.K=K=ctypes.WinDLL('kernel32',use_last_error=True);self.W=W
  K.OpenJobObjectW.argtypes=[W.DWORD,W.BOOL,W.LPCWSTR];K.OpenJobObjectW.restype=W.HANDLE;K.OpenProcess.argtypes=[W.DWORD,W.BOOL,W.DWORD];K.OpenProcess.restype=W.HANDLE
  K.GetCurrentProcess.restype=W.HANDLE;K.CloseHandle.argtypes=[W.HANDLE];K.IsProcessInJob.argtypes=[W.HANDLE,W.HANDLE,ctypes.POINTER(W.BOOL)];K.QueryInformationJobObject.argtypes=[W.HANDLE,ctypes.c_int,ctypes.c_void_p,W.DWORD,ctypes.c_void_p]
  K.GetProcessTimes.argtypes=[W.HANDLE,*[ctypes.POINTER(W.FILETIME)]*4];K.WaitForSingleObject.argtypes=[W.HANDLE,W.DWORD];K.WaitForSingleObject.restype=W.DWORD;K.GetActiveProcessorCount.argtypes=[W.WORD];K.GetActiveProcessorCount.restype=W.DWORD
  K.CreateEventW.argtypes=[ctypes.c_void_p,W.BOOL,W.BOOL,W.LPCWSTR];K.CreateEventW.restype=W.HANDLE;K.SetEvent.argtypes=[W.HANDLE];K.WaitForMultipleObjects.argtypes=[W.DWORD,ctypes.POINTER(W.HANDLE),W.BOOL,W.DWORD];K.WaitForMultipleObjects.restype=W.DWORD;K.TerminateJobObject.argtypes=[W.HANDLE,W.UINT];K.TerminateProcess.argtypes=[W.HANDLE,W.UINT]
  self.name=caps.get('worker',{}).get('jobName');C.need(type(self.name) is str and re.fullmatch(r'Local\\[A-Za-z0-9_.-]{1,180}',self.name),'NORMAL_WINDOWS_JOB_NAME')
  try:
   self.job=K.OpenJobObjectW(4|8,False,self.name);C.need(bool(self.job),'NORMAL_WINDOWS_OWN_JOB_HANDLE');self.parent=K.OpenProcess(0x1000|0x100000,False,ctx['supervisorPID']);C.need(bool(self.parent),'NORMAL_WINDOWS_PARENT_HANDLE')
   C.need(os.getppid()==ctx['supervisorPID'] and self.start(self.parent)==ctx['supervisorStartIdentity'] and K.WaitForSingleObject(self.parent,0)==258,'NORMAL_WINDOWS_LIVE_PARENT')
   member=W.BOOL();C.need(K.IsProcessInJob(self.parent,self.job,ctypes.byref(member)) and not member.value,'NORMAL_WINDOWS_DEDICATED_WORKER_JOB')
   self.observe();self.cancel=K.CreateEventW(None,True,False,None);C.need(bool(self.cancel),'NORMAL_WINDOWS_DEADLINE_EVENT')
   def watch():
    handles=(W.HANDLE*2)(self.cancel,self.parent);ms=max(0,min(0xfffffffe,(end-time.monotonic_ns())//1000000));result=K.WaitForMultipleObjects(2,handles,False,int(ms))
    if result!=0:
     if not K.TerminateJobObject(self.job,124):K.TerminateProcess(K.GetCurrentProcess(),124)
   self.thread=threading.Thread(target=watch,name='own-normal-original-deadline',daemon=True);self.thread.start();C._remaining(end)
  except BaseException:self.close();raise
 def start(self,handle):
  t=[self.W.FILETIME() for _ in range(4)];self.C.need(self.K.GetProcessTimes(handle,*[ctypes.byref(x) for x in t]),'NORMAL_WINDOWS_PROCESS_START');return 'FILETIME:'+str((t[0].dwHighDateTime<<32)|t[0].dwLowDateTime)
 def observe(self):
  C=self.C;K=self.K;W=self.W;U=ctypes.c_size_t
  class Basic(ctypes.Structure):_fields_=[('ProcessTime',ctypes.c_longlong),('JobTime',ctypes.c_longlong),('Flags',W.DWORD),('MinWS',U),('MaxWS',U),('ActiveProcesses',W.DWORD),('Affinity',U),('Priority',W.DWORD),('Scheduling',W.DWORD)]
  class IO(ctypes.Structure):_fields_=[(n,ctypes.c_ulonglong) for n in ('ReadOps','WriteOps','OtherOps','ReadBytes','WriteBytes','OtherBytes')]
  class Extended(ctypes.Structure):_fields_=[('Basic',Basic),('IO',IO),('ProcessMemory',U),('JobMemory',U),('PeakProcessMemory',U),('PeakJobMemory',U)]
  class CPU(ctypes.Structure):_fields_=[('Flags',W.DWORD),('Rate',W.DWORD)]
  class IDs(ctypes.Structure):_fields_=[('Assigned',W.DWORD),('Listed',W.DWORD),('IDs',U*256)]
  limits=Extended();cpu=CPU();ids=IDs();member=W.BOOL();C.need(K.IsProcessInJob(K.GetCurrentProcess(),self.job,ctypes.byref(member)) and member.value,'NORMAL_WINDOWS_CURRENT_MEMBERSHIP')
  C.need(K.QueryInformationJobObject(self.job,9,ctypes.byref(limits),ctypes.sizeof(limits),None) and K.QueryInformationJobObject(self.job,15,ctypes.byref(cpu),ctypes.sizeof(cpu),None) and K.QueryInformationJobObject(self.job,3,ctypes.byref(ids),ctypes.sizeof(ids),None),'NORMAL_WINDOWS_KERNEL_READBACK')
  C.need(ids.Listed==ids.Assigned==1 and ids.IDs[0]==os.getpid(),'NORMAL_WINDOWS_MAIN_WORKER_ONLY');logical=int(K.GetActiveProcessorCount(0xffff));C.need(logical>0 and cpu.Flags==5 and 0<cpu.Rate<=10000,'NORMAL_WINDOWS_CPU_RATE')
  C.need(limits.Basic.Flags&0x2208==0x2208 and not limits.Basic.Flags&0x1800,'NORMAL_WINDOWS_NO_BREAKAWAY_KILL_CLOSE')
  C.need(K.WaitForSingleObject(self.parent,0)==258 and self.start(self.parent)==self.ctx['supervisorStartIdentity'],'NORMAL_WINDOWS_PARENT_CHANGED')
  return {'pid':os.getpid(),'processStartIdentity':self.start(K.GetCurrentProcess()),'jobName':self.name,'memoryMaxBytes':int(limits.JobMemory),'tasksMax':int(limits.Basic.ActiveProcesses),'cpuRate':int(cpu.Rate),'logicalHostCpu':logical,'effectiveCpuCores':cpu.Rate*logical/10000,'limitFlags':int(limits.Basic.Flags),'supervisorPID':self.ctx['supervisorPID'],'supervisorStartIdentity':self.start(self.parent),'hardOuterDeadlineNs':self.end}
 def close(self):
  if self.cancel:self.K.SetEvent(self.cancel)
  if self.thread:self.thread.join(timeout=max(0,min(.25,(self.end-time.monotonic_ns())/1e9)))
  alive=self.thread is not None and self.thread.is_alive()
  if not alive:
   for handle in (self.cancel,self.parent,self.job):
    if handle:self.K.CloseHandle(handle)
   self.cancel=self.parent=self.job=None
  self.C.need(not alive,'NORMAL_WINDOWS_DEADLINE_WATCH_TERMINAL')

def validate_current(C,ctx,admission,profile,pins,current,caps,hashes,schema):
 C._deadline_values(ctx,current['observedNowNs']);project=ctx['projectId'];C.schema_check(admission,schema['$defs']['consumerAdmission'])
 C.need(profile.get('schema')=='sdk11-own-normal-input-profile/v1' and profile.get('state')=='ADMITTED_SOURCE_PROFILE' and profile.get('projectId')==project and profile.get('repository')==ctx['repository'] and profile.get('rid')=='win-x64','NORMAL_WINDOWS_OWN_PROFILE')
 C.need(type(profile.get('rowSeconds')) is int and 0<profile['rowSeconds']<=C.BUDGETS[project] and ctx['deadlineMonotonicNs']-ctx['rowStartedMonotonicNs']<=profile['rowSeconds']*10**9,'NORMAL_WINDOWS_OWN_BUDGET')
 for k in ('memoryMaxBytes','tasksMax','cpuCores','scratchMaxBytes'):C.need(type(profile.get(k)) is int and profile[k]>0,'NORMAL_WINDOWS_OWN_PROFILE_LIMITS')
 C.need(profile['cpuCores']<=2 and profile['tasksMax']<=256 and profile.get('swapMaxBytes') is None,'NORMAL_WINDOWS_OWN_PROFILE_LIMITS')
 C.need(current['memoryMaxBytes']==profile['memoryMaxBytes'] and current['tasksMax']==profile['tasksMax'] and 0<current['effectiveCpuCores']<=profile['cpuCores'],'NORMAL_WINDOWS_ACTUAL_OWN_CAPS')
 C.need(current['cpuRate']==max(1,min(10000,int(10000*profile['cpuCores']/current['logicalHostCpu']))),'NORMAL_WINDOWS_ACTUAL_OWN_CPU_RATE')
 C.need(admission['projectId']==project and admission['producerFactSha256']==FACT,'NORMAL_WINDOWS_OWN_ADMISSION');b=admission['admittedFor'];C.need(b['hostClass']==HOST and b['rid']=='win-x64' and b['memberManifestSha256']==MANIFEST,'NORMAL_WINDOWS_ADMISSION_HOST_RID')
 C.need(b['profileSha256']==hashes['profile'] and b['controllerSha256']==hashes['controller'] and b['contractSha256']==hashes['contract'] and b['sourcePinTableSha256']==hashlib.sha256(C.canonical(pins['sourcePins'])).hexdigest(),'NORMAL_WINDOWS_SOURCE_PROFILE_HASH')
 C.need(pins.get('schema')=='sdk11-own-source-pins/v1' and pins.get('state')=='EXACT_SOURCE_REVIEWED' and pins.get('projectId')==project and pins.get('repository')==ctx['repository'],'NORMAL_WINDOWS_SOURCE_PINS')
 C.need(current['hostClass']==HOST and current['repository']==ctx['repository'] and current['commit']==ctx['expectedSourceCommit'] and current['tree']==ctx['expectedSourceTree'],'NORMAL_WINDOWS_CURRENT_SOURCE')
 C.need(all(admission['currentExecution'][k]==current[k] and current[k] for k in ('runId','job','attempt','instanceId')) and admission['currentExecution']['ownCapsEvidenceSha256']==hashes['capsEvidence'],'NORMAL_WINDOWS_CURRENT_EXECUTION')
 C.need(caps.get('schema')=='sdk11-own-current-cap-evidence/v1' and caps.get('projectId')==project and caps.get('repository')==ctx['repository'] and caps.get('sourceCommit')==current['commit'] and caps.get('sourceTree')==current['tree'] and caps.get('profileSha256')==hashes['profile'] and caps.get('controllerSha256')==hashes['controller'],'NORMAL_WINDOWS_CAP_EVIDENCE')
 C.need(caps.get('bootstrap')==current['bootstrap'],'NORMAL_WINDOWS_CURRENT_BOOTSTRAP');worker=caps.get('worker',{});held=caps.get('heldBeforeExec',{});supervisor=caps.get('supervisor',{})
 for row in (worker,held):C.need(all(row.get(k)==current[k] for k in ('pid','processStartIdentity','jobName','memoryMaxBytes','tasksMax','cpuRate','logicalHostCpu')),'NORMAL_WINDOWS_HELD_WORKER_IDENTITY')
 C.need(held.get('state')=='SUSPENDED' and held.get('membershipBeforeRelease') is True and held.get('retainedStartHandle') is True,'NORMAL_WINDOWS_HELD_BEFORE_EXEC')
 C.need(supervisor.get('pid')==current['supervisorPID']==ctx['supervisorPID'] and supervisor.get('processStartIdentity')==current['supervisorStartIdentity']==ctx['supervisorStartIdentity'] and supervisor.get('deadlineMonotonicNs')==ctx['deadlineMonotonicNs']==current['hardOuterDeadlineNs'],'NORMAL_WINDOWS_ORIGINAL_SUPERVISOR')
 C.need(caps.get('rowStartedMonotonicNs')==ctx['rowStartedMonotonicNs'] and caps.get('deadlineMonotonicNs')==ctx['deadlineMonotonicNs'],'NORMAL_WINDOWS_CLOCK_EVIDENCE');return True

def host(C,ctx,own):
 import winreg
 C.need(sys.version_info[:3]==(3,12,10) and platform.machine().lower() in ('amd64','x86_64') and os.environ.get('RUNNER_ENVIRONMENT')=='github-hosted' and os.environ.get('RUNNER_OS')=='Windows','NORMAL_WINDOWS_CURRENT_HOST')
 v=sys.getwindowsversion();C.need(v.product_type==3 and v.build==26100,'NORMAL_WINDOWS_CURRENT_HOST')
 with winreg.OpenKey(winreg.HKEY_LOCAL_MACHINE,r'SOFTWARE\Microsoft\Windows NT\CurrentVersion') as k:name=winreg.QueryValueEx(k,'ProductName')[0];build=winreg.QueryValueEx(k,'CurrentBuildNumber')[0];ubr=winreg.QueryValueEx(k,'UBR')[0]
 C.need('Windows Server 2025' in name and build=='26100' and (os.environ.get('ImageOS')=='win25' or (os.environ.get('ImageOS')=='win25-vs2026' and os.environ.get('ImageVersion')=='20261103.298.1')),'NORMAL_WINDOWS_CURRENT_HOST')
 current=own.observe();current.update(hostClass=HOST,repository=os.environ.get('GITHUB_REPOSITORY'),runId=os.environ.get('GITHUB_RUN_ID'),job=os.environ.get('GITHUB_JOB'),attempt=os.environ.get('GITHUB_RUN_ATTEMPT'),instanceId=os.environ.get('RUNNER_NAME'),imageOS=os.environ.get('ImageOS'),imageVersion=os.environ.get('ImageVersion'),osVersion=name,kernelBuild=build+'.'+str(ubr),architecture='x64',bootstrap={'pythonVersion':platform.python_version(),'pythonExeSha256':C.digest(Path(sys.executable).resolve()),'gitSha256':C.digest('C:/Program Files/Git/cmd/git.exe')});return current

def git(C,argv,cwd,end,limit=1048576):
 env={k:v for k,v in os.environ.items() if k.upper() in ('SYSTEMROOT','WINDIR','TEMP','TMP')};env.update(GIT_CONFIG_NOSYSTEM='1',GIT_CONFIG_GLOBAL='NUL',GIT_TERMINAL_PROMPT='0',GCM_INTERACTIVE='Never')
 r=subprocess.run(['C:/Program Files/Git/cmd/git.exe','-C',str(cwd),*argv],capture_output=True,env=env,timeout=min(10,C._remaining(end)));C.need(r.returncode==0 and len(r.stdout)+len(r.stderr)<=limit,'NORMAL_WINDOWS_SOURCE_TOOL');return r.stdout

def preflight(C,ctx,own,paths,profile,caps,hashes,c,fact,schema,end):
 checkout=Path(ctx['checkout']).resolve();C.need(str(checkout)==str(Path(os.environ['GITHUB_WORKSPACE']).resolve()),'NORMAL_WINDOWS_CURRENT_CHECKOUT');main=getattr(sys.modules.get('__main__'),'__file__',None);C.need(main and Path(main).resolve()==paths['controller'].resolve(),'NORMAL_CAPPED_CALLER_CONTROLLER')
 current=host(C,ctx,own);lines=git(C,['rev-parse','HEAD','HEAD^{tree}'],checkout,end,4096).decode().splitlines();C.need(len(lines)==2 and os.environ.get('GITHUB_SHA')==lines[0],'NORMAL_WINDOWS_EVENT_SOURCE');current.update(commit=lines[0],tree=lines[1],observedNowNs=time.monotonic_ns());C.need(not git(C,['status','--porcelain=v1','--untracked-files=all'],checkout,end),'NORMAL_SOURCE_NOT_CLEAN')
 pins=C._read(paths['sourcePins'],1048576);actual={}
 for row in git(C,['ls-tree','-r','-z','HEAD'],checkout,end).split(b'\0'):
  if not row:continue
  meta,name=row.split(b'\t',1);mode,kind,blob=meta.decode().split();C.need(kind=='blob' and mode in ('100644','100755'),'NORMAL_SOURCE_MODE');actual[name.decode()]={'path':name.decode(),'mode':mode,'gitBlob':blob}
 selfpin=paths['sourcePins'].relative_to(checkout).as_posix();C.need(selfpin in actual,'NORMAL_SOURCE_PINS_NOT_TRACKED');actual.pop(selfpin);expected={x['path']:x for x in pins.get('sourcePins',[])};C.need(len(expected)==len(pins.get('sourcePins',[])) and actual==expected,'NORMAL_SOURCE_PIN_TABLE')
 for key in ('controller','contract','profile'):
  name=paths[key].relative_to(checkout).as_posix();C.need(name in actual,'NORMAL_BINDING_NOT_TRACKED');C.validate_source_file(paths[key],actual[name],git(C,['show','HEAD:'+name],checkout,end))
 admission=C._read(paths['admission'],65536);validate_current(C,ctx,admission,profile,pins,current,caps,hashes,schema);C._remaining(end);return current,admission

def measure_cpu(C,root):
 f=C._load('sdk11_ci_facts',C.PINS['windowsFactHelperSha256']);digest=C.digest
 def write(path,value):
  with Path(path).open('x',encoding='utf-8') as stream:json.dump(value,stream,indent=2)

 from ctypes import wintypes as W
 k=ctypes.WinDLL('kernel32',use_last_error=True);k.VirtualAlloc.argtypes=[ctypes.c_void_p,ctypes.c_size_t,W.DWORD,W.DWORD];k.VirtualAlloc.restype=ctypes.c_void_p;k.VirtualProtect.argtypes=[ctypes.c_void_p,ctypes.c_size_t,W.DWORD,ctypes.POINTER(W.DWORD)];k.VirtualFree.argtypes=[ctypes.c_void_p,ctypes.c_size_t,W.DWORD];k.GetCurrentProcess.restype=W.HANDLE;k.GetCurrentThread.restype=W.HANDLE;k.GetProcessAffinityMask.argtypes=[W.HANDLE,ctypes.POINTER(ctypes.c_size_t),ctypes.POINTER(ctypes.c_size_t)];k.SetThreadAffinityMask.argtypes=[W.HANDLE,ctypes.c_size_t];k.SetThreadAffinityMask.restype=ctypes.c_size_t;k.FlushInstructionCache.argtypes=[W.HANDLE,ctypes.c_void_p,ctypes.c_size_t]
 code=bytes.fromhex('5389c889d10fa241890041895804418948084189500c5bc3');memory=k.VirtualAlloc(None,4096,0x3000,4);f.need(memory,'CPU_CPUID_ALLOCATION');old=W.DWORD();records=[];old_affinity=0
 try:
  ctypes.memmove(memory,code,len(code));f.need(k.VirtualProtect(memory,4096,0x20,ctypes.byref(old)) and k.FlushInstructionCache(k.GetCurrentProcess(),memory,len(code)),'CPU_CPUID_RX_POLICY')
  call=ctypes.WINFUNCTYPE(None,W.DWORD,W.DWORD,ctypes.POINTER(W.DWORD))(memory);pm=ctypes.c_size_t();sm=ctypes.c_size_t();f.need(k.GetProcessAffinityMask(k.GetCurrentProcess(),ctypes.byref(pm),ctypes.byref(sm)) and pm.value,'CPU_AFFINITY')
  k.GetActiveProcessorGroupCount.restype=W.WORD;f.need(k.GetActiveProcessorGroupCount()==1,'CPU_GROUP_SCOPE_UNSUPPORTED')
  for index in range(64):
   if not(pm.value&(1<<index)):continue
   previous=k.SetThreadAffinityMask(k.GetCurrentThread(),1<<index);f.need(previous,'CPU_AFFINITY');old_affinity=previous;v=(W.DWORD*4)();call(0,0,v);f.need(v[0]>=1,'CPU_CPUID_LEAF');call(1,0,v);ecx=int(v[2]);call(0x80000000,0,v);f.need(v[0]>=0x80000001,'CPU_CPUID_LEAF');call(0x80000001,0,v);ext=int(v[2]);f.need(ecx&((1<<0)|(1<<9)|(1<<13)|(1<<19)|(1<<20)|(1<<23))==((1<<0)|(1<<9)|(1<<13)|(1<<19)|(1<<20)|(1<<23)) and ext&1,'Q_CPU_V2_BEFORE_SDK');records.append({'processor':index,'leaf1Ecx':ecx,'extendedEcx':ext});f.need(k.SetThreadAffinityMask(k.GetCurrentThread(),old_affinity),'CPU_AFFINITY_RESTORE');old_affinity=0
 finally:
  if old_affinity:k.SetThreadAffinityMask(k.GetCurrentThread(),old_affinity)
  k.VirtualFree(memory,0,0x8000)
 write(root/'cpu-evidence.json',{'method':'FixedCPUIDthunkRWtoRX, noRWX/nohostpolicychange, perallowedprocessor, no.NETbootstrap','codeHex':code.hex(),'codeSha256':hashlib.sha256(code).hexdigest(),'processors':records})
 return {'method':'FIXED_CPUID_PER_ALLOWED_LOGICAL_PROCESSOR','processorCount':len(records),'evidenceSha256':digest(root/'cpu-evidence.json'),'features':f.FEATURES}

def execute(C,directory,ctx,inspect=False):
 started=time.monotonic_ns();end=C._deadline_values(ctx,started);C.need(os.name=='nt','NORMAL_WINDOWS_CURRENT_HOST');a=C._load('qualification_input_guard',C.PINS['guardSha256']);checkout=Path(ctx['checkout']).resolve();temp=Path(os.environ.get('RUNNER_TEMP','')).resolve();C.need(os.environ.get('RUNNER_TEMP') and temp.is_dir(),'NORMAL_WINDOWS_RUNNER_TEMP')
 paths={k:a.scoped(ctx[k],checkout if k in ('controller','contract','profile','sourcePins') else temp) for k in ('controller','contract','profile','sourcePins','admission','capsEvidence')};caps=C._read(paths['capsEvidence'],65536);profile=C._read(paths['profile'],65536);hashes={k:C.digest(p) for k,p in paths.items()};own=OwnJob(C,ctx,caps,end);allocation=None;identity=None
 try:
  c,fact,schema=documents(C);current,admission=preflight(C,ctx,own,paths,profile,caps,hashes,c,fact,schema,end)
  # Reuse the fixed source-pinned per-processor CPUID measurement, no SDK bootstrap.
  cpuRoot=a.scoped(paths['capsEvidence'].parent/('normal-cpu-'+str(time.monotonic_ns())),temp,absent=True);cpuRoot.mkdir();cpu=measure_cpu(C,cpuRoot);C._remaining(end)
  if inspect:
   sdk=a.scoped(directory,temp);a.verify_tree(sdk,c['members'],'win-x64',full=True);raw=None
  else:
   allocation=Path(directory).absolute();C.need(allocation.parent==temp and re.fullmatch('sdk11-normal-'+ctx['projectId']+'-[A-Za-z0-9_.-]{1,160}',allocation.name),'NORMAL_FRESH_SCOPE');a.scoped(allocation,temp,absent=True);allocation.mkdir();identity=(allocation.stat().st_dev,allocation.stat().st_ino)
   values=[own.W.DWORD() for _ in range(4)];own.K.GetDiskFreeSpaceW.argtypes=[own.W.LPCWSTR,*[ctypes.POINTER(own.W.DWORD)]*4];C.need(own.K.GetDiskFreeSpaceW(allocation.anchor,*[ctypes.byref(x) for x in values]),'NORMAL_WINDOWS_ALLOCATION_UNIT');unit=values[0].value*values[1].value;C.need(0<unit<=1048576 and unit&(unit-1)==0,'NORMAL_WINDOWS_ALLOCATION_UNIT')
   expected=(c['bytes']+unit-1)//unit*unit+sum((x['bytes']+unit-1)//unit*unit for x in c['members'])+len(c['members'])*unit+1048576;C.need(expected<=profile['scratchMaxBytes'] and shutil.disk_usage(allocation).free>=expected,'NORMAL_WINDOWS_SCRATCH_LEDGER')
   archive=allocation/'official-archive';raw=C._download(c,archive,end);sdk=allocation/'sdk';members=a.extract_members(archive,sdk,'win-x64');C.need(members==c['members'],'NORMAL_MEMBER_POSTIMAGE');a.verify_tree(sdk,c['members'],'win-x64',full=True);C._remaining(end);archive.unlink()
  again=own.observe();C.need(all(again[k]==current[k] for k in ('pid','processStartIdentity','jobName','memoryMaxBytes','tasksMax','cpuRate','logicalHostCpu')),'NORMAL_CAPS_CHANGED');C._remaining(end)
  receipt={'schema':'sdk11-shared-normal-input-receipt/v1','state':'OWN_CURRENT_FULL_INPUT_IDENTITY_VERIFIED' if inspect else 'OWN_CURRENT_CALLER_INPUT_VERIFIED_NO_SDK_EXECUTION','projectId':ctx['projectId'],'rid':'win-x64','sdk':'11.0.100','runtime':'11.0.0','normalCatalogSha256':C.PINS['catalogSha256'],'producerFactSha256':FACT,'producerAcceptanceSha256':ACCEPT,'producerQualifiedOn':fact['qualifiedOn'],'producerSource':fact['source'],'ownCurrent':current,'ownBindingFileHashes':hashes,'rawArchive':raw,'memberManifestSha256':MANIFEST,'namespace':{'rawHeaders':5480,'physicalFiles':5480,'expandedFileBytes':888661156,'physicalLinks':0},'notices':[x for x in c['members'] if re.match(r'(?i)(license|third.?party.?notices)',Path(x['path']).name)],'criticalMembers':[x for x in c['members'] if x['path'] in C.critical_names('win-x64')],'cpu':cpu,'absoluteOriginalDeadlineNs':end,'inputStartedMonotonicNs':started,'completedMonotonicNs':time.monotonic_ns(),'SDKExecutions':0,'SDKPathOrGitHubEnvironmentExports':0,'SDKCacheOrArtifactUploads':0,'boundary':'Own current input only; no native package, product or global readiness. Native watchdog retains only this dedicated Job and live parent and never extends the original clock.'}
  receipt.update(consumerAdmission=admission,originalRowStartedMonotonicNs=ctx['rowStartedMonotonicNs'],effectiveWatchDeadlineNs=end)
  encoded=C.canonical(receipt);C.need(len(encoded)<=1048576,'NORMAL_RECEIPT_CAP')
  if not inspect:
   with (allocation/'input-receipt.json').open('xb') as out:out.write(encoded);out.flush();os.fsync(out.fileno())
  C._remaining(end);return receipt if inspect else (sdk,receipt)
 except BaseException as exc:
  state='NO_ALLOCATION'
  if allocation is not None:
   try:
    C._remaining(end);s=allocation.lstat();C.need((s.st_dev,s.st_ino)==identity and not s.st_file_attributes&0x400 and allocation.parent==temp,'NORMAL_CLEANUP_SCOPE');shutil.rmtree(allocation);C._remaining(end);state='OWN_FRESH_ALLOCATION_REMOVED'
   except Exception:state='UNKNOWN_OR_DEADLINE_PARTIAL_RETAINED'
  exc.normalInputCleanup={'state':state,'allocationCreated':allocation is not None};raise
 finally:own.close();C._remaining(end)
