from pathlib import Path
import argparse,ast,copy,ctypes,ctypes.wintypes,hashlib,importlib.util,json,sys,time,types
sys.dont_write_bytecode=True;parser=argparse.ArgumentParser();parser.add_argument('--source-root',type=Path,default=Path(__file__).resolve().parent);parser.add_argument('--out',type=Path);cli=parser.parse_args();T=cli.source_root
def load(name,path):
 s=importlib.util.spec_from_file_location(name,path);m=importlib.util.module_from_spec(s);sys.modules[name]=m;s.loader.exec_module(m);return m
C=load('common_delta_source',T/'check_dotnet11.py');W=load('windows_delta_source',T/'normal_windows_input.py')
def check(v,c):
 if not v:raise RuntimeError(c)
start=time.monotonic();build={'unchangedLinuxEntryCanonicalSHA256':'1864928a565fb75af51112055840356e9a2e5bde1e8902cc59980329b5e40e97','unchangedDefinitions':[None]*31};cat=json.loads((T/'sdk11-normal-inputs.lock.json').read_bytes());schema=json.loads((T/'dotnet11-host-qualification.schema.json').read_bytes());fact=json.loads((T/'sdk11-normal/accepted-windows-fact.json').read_bytes());accept=json.loads((T/'sdk11-normal/accepted-windows-acceptance.json').read_bytes());W.validate_catalog(C,cat['rids']['win-x64'],fact,accept);C._documents('win-x64');C._documents('linux-x64')
check(hashlib.sha256(C.canonical(cat['rids']['linux-x64'])).hexdigest()==build['unchangedLinuxEntryCanonicalSHA256'],'LINUX_ENTRY_CHANGED')
def baseline(project,memory,tasks):
 end=100_000_000_000;ctx={'projectId':project,'repository':'synthetic/repo','checkout':'synthetic','controller':'controller','contract':'contract','profile':'profile','sourcePins':'pins','admission':'admission','capsEvidence':'caps','expectedSourceCommit':'a'*40,'expectedSourceTree':'b'*40,'rowStartedMonotonicNs':1,'deadlineMonotonicNs':end,'supervisorPID':100,'supervisorStartIdentity':'FILETIME:1'}
 profile={'schema':'sdk11-own-normal-input-profile/v1','state':'ADMITTED_SOURCE_PROFILE','projectId':project,'repository':ctx['repository'],'rid':'win-x64','rowSeconds':min(C.BUDGETS[project],600),'memoryMaxBytes':memory,'tasksMax':tasks,'cpuCores':2,'scratchMaxBytes':2*1024**3,'swapMaxBytes':None};pins={'schema':'sdk11-own-source-pins/v1','state':'EXACT_SOURCE_REVIEWED','projectId':project,'repository':ctx['repository'],'sourcePins':[]};hashes={k:'c'*64 for k in ('profile','controller','contract','capsEvidence')}
 cur={'observedNowNs':10,'hostClass':W.HOST,'repository':ctx['repository'],'commit':ctx['expectedSourceCommit'],'tree':ctx['expectedSourceTree'],'runId':'fixture','job':'consumer','attempt':'1','instanceId':'synthetic','pid':101,'processStartIdentity':'FILETIME:2','jobName':'Local\\synthetic-own','memoryMaxBytes':memory,'tasksMax':tasks,'cpuRate':1250,'logicalHostCpu':16,'effectiveCpuCores':2,'supervisorPID':100,'supervisorStartIdentity':'FILETIME:1','hardOuterDeadlineNs':end,'bootstrap':{'synthetic':True}}
 keys=('pid','processStartIdentity','jobName','memoryMaxBytes','tasksMax','cpuRate','logicalHostCpu');held={k:cur[k] for k in keys};held.update(state='SUSPENDED',membershipBeforeRelease=True,retainedStartHandle=True);caps={'schema':'sdk11-own-current-cap-evidence/v1','projectId':project,'repository':ctx['repository'],'sourceCommit':cur['commit'],'sourceTree':cur['tree'],'profileSha256':hashes['profile'],'controllerSha256':hashes['controller'],'bootstrap':cur['bootstrap'],'worker':{k:cur[k] for k in keys},'heldBeforeExec':held,'supervisor':{'pid':100,'processStartIdentity':'FILETIME:1','deadlineMonotonicNs':end},'rowStartedMonotonicNs':1,'deadlineMonotonicNs':end}
 adm={'schema':'sdk11-consumer-host-admission/v1','state':'ADMITTED_EXACT_SUPPORTED_HOST_CLASS','projectId':project,'producerFactSha256':W.FACT,'admittedFor':{'hostClass':W.HOST,'rid':'win-x64','sdk':'11.0.100','runtime':'11.0.0','memberManifestSha256':W.MANIFEST,'contractSha256':hashes['contract'],'sourcePinTableSha256':hashlib.sha256(C.canonical([])).hexdigest(),'controllerSha256':hashes['controller'],'profileSha256':hashes['profile']},'currentExecution':{**{k:cur[k] for k in ('runId','job','attempt','instanceId')},'ownCapsEvidenceSha256':hashes['capsEvidence']},'identityRule':'QUALIFIED_ON_IS_HISTORICAL_PRODUCER_INSTANCE_CURRENT_CONSUMER_JOB_MAY_DIFFER'};return [ctx,adm,profile,pins,cur,caps,hashes,schema]
positive=[]
for project,memory,tasks in [('01',2*1024**3,32),('02',4*1024**3,64),('03',4*1024**3,64)]:check(W.validate_current(C,*baseline(project,memory,tasks)),'OWN_POSITIVE');positive.append(project)
negatives=[]
for name,index,path,value in [('wrong-fact',1,['producerFactSha256'],'d'*64),('wrong-rid',1,['admittedFor','rid'],'linux-x64'),('wrong-host',4,['hostClass'],'LocalWindows'),('source-mismatch',4,['commit'],'e'*40),('borrowed-memory',4,['memoryMaxBytes'],4*1024**3),('borrowed-tasks',4,['tasksMax'],64),('CPU-rate',4,['cpuRate'],1249),('held-start',5,['heldBeforeExec','processStartIdentity'],'FILETIME:999'),('held-membership',5,['heldBeforeExec','membershipBeforeRelease'],False),('parent-start',5,['supervisor','processStartIdentity'],'FILETIME:9'),('deadline-reset',5,['deadlineMonotonicNs'],101_000_000_000),('bootstrap-mismatch',5,['bootstrap'],{}),('instance',1,['currentExecution','instanceId'],'wrong'),('profile-controller',1,['admittedFor','controllerSha256'],'d'*64),('expired',4,['observedNowNs'],101_000_000_000)]:
 args=baseline('01',2*1024**3,32);target=args[index]
 for key in path[:-1]:target=target[key]
 target[path[-1]]=value
 try:W.validate_current(C,*args)
 except C.AdmissionError:negatives.append(name)
 else:raise RuntimeError('ACCEPTED_'+name)
for name,path,value in [('producer-source',['producerCommit'],'f'*40),('raw-hash',['input','sha512'],'0'*128),('raw-size',['input','bytes'],1),('member-hash',['input','memberManifestSha256'],'f'*64),('fact-pin',['factSha256'],'f'*64)]:
 entry=copy.deepcopy(cat['rids']['win-x64']);target=entry
 for key in path[:-1]:target=target[key]
 target[path[-1]]=value
 try:
  if name=='fact-pin':C.need(entry['factSha256']==W.FACT,'NORMAL_WINDOWS_FACT_AUTHORITY')
  W.validate_catalog(C,entry,fact,accept)
 except C.AdmissionError:negatives.append(name)
 else:raise RuntimeError('ACCEPTED_'+name)
# Exercise the actual nested watchdog code with fake kernel results only.
tree=ast.parse((T/'normal_windows_input.py').read_bytes());watch=next(n for n in ast.walk(tree) if isinstance(n,ast.FunctionDef) and n.name=='watch');code=compile(ast.fix_missing_locations(ast.Module(body=[watch],type_ignores=[])),'actual-source-watch','exec');watchCases=[]
for result,terminateOK in [(0,True),(1,True),(258,True),(0xffffffff,True),(258,False)]:
 calls=[]
 class Kernel:
  def WaitForMultipleObjects(self,count,handles,all_,ms):check(count==2 and not all_ and ms==500,'ORIGINAL_WALL');return result
  def TerminateJobObject(self,handle,exit):calls.append('job');check(handle==12 and exit==124,'EXACT_OWN_JOB');return terminateOK
  def GetCurrentProcess(self):return 99
  def TerminateProcess(self,handle,exit):calls.append('self');check(handle==99 and exit==124,'SELF_FALLBACK');return True
 env={'K':Kernel(),'W':ctypes.wintypes,'self':types.SimpleNamespace(cancel=10,parent=11,job=12),'end':500_000_000,'time':types.SimpleNamespace(monotonic_ns=lambda:0)};exec(code,env);env['watch']();check(calls==([] if result==0 else ['job'] if terminateOK else ['job','self']),'WATCH_FAIL_CLOSED');watchCases.append({'result':result,'actions':calls})
nativePath=T/cat['nativeInputFactsFile'];nativeBody=nativePath.read_bytes();check(hashlib.sha256(nativeBody).hexdigest()==cat['nativeInputFactsSha256'],'NATIVE_CATALOG_IDENTITY');native=json.loads(nativeBody);refs=[]
for pkg in native['packages']:refs.extend([pkg['archiveMemberInventory'],*pkg['originalData'],pkg['actualNuGetVerification']['retainedReport']])
refs.extend(native['completeMetadataSnapshots']);refs.extend(native['actualCurationEvidence']);refs.extend(x['retainedBytes'] for x in native['hiddenMetadataRecovery'])
for row in refs:
 rel=Path(row['file']);check(not rel.is_absolute() and '..' not in rel.parts,'PORTABLE_REFERENCE');body=(T/rel).read_bytes();check(len(body)==row['bytes'] and hashlib.sha256(body).hexdigest()==row['sha256'],'PORTABLE_NATIVE_FACT_BYTES')
check(len(native['packages'])==3 and native['windowsNativeNuGetState']=='NOT_ADMITTED_BY_WINDOWS_HOST_QUALIFICATION' and native['SDK_READY'] is False,'NATIVE_HOST_SEPARATION')
check(time.monotonic()-start<30,'FIXTURE30');out={'state':'COMMON_WINDOWS_DELTA_SOURCE_FIXTURES_PASS','optimized':not __debug__,'actualWindowsProducerDocuments':True,'portableNativeReferencesVerified':len(refs),'linuxEntryUnchanged':True,'ownProfilePositives':positive,'denials':negatives,'originalDeadlineWatchdogFakeKernelCases':watchCases,'unchangedDefinitions':len(build['unchangedDefinitions']),'SDK':0,'restore':0,'qualification':0,'network':0,'nativeJobs':0,'commonWindowsRuntime':'UNEXECUTED_CONSUMER_OWN_GATE_REQUIRED','elapsedSeconds':time.monotonic()-start};print(json.dumps(out))
if cli.out:cli.out.write_text(json.dumps(out,indent=2)+'\n',encoding='utf-8')
