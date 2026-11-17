"""Closed typed facts and ownconsumer04 handshake. Pure stdlib; no execution on import."""
from __future__ import annotations
import hashlib,json,re
HOSTS={'win-x64':'GitHubHostedWindowsServer2025x64','linux-x64':'GitHubHostedUbuntu24.04x64'}
MANIFESTS={'win-x64':'7eb452d5eaa748773eb0b12d1abc8da1a9f1c192b06444dc88c6511de56b63c3','linux-x64':'d411111d23492b4d101dd62851d1d1fedf3a4badc057d999aedc155ae4cc103a'}
RAW={'win-x64':('https://builds.dotnet.microsoft.com/dotnet/Sdk/11.0.100/dotnet-sdk-11.0.100-win-x64.zip',337835326,'5cdd9122c84873f090038548ebe8a4786e5c50a6b1b9792ca2c6dab82fd74a0d7f1d6cdf59e7dcd25e4903dd44f37af5d7ed73ecd3bca4d0cce948b5572452c3'),'linux-x64':('https://builds.dotnet.microsoft.com/dotnet/Sdk/11.0.100/dotnet-sdk-11.0.100-linux-x64.tar.gz',211463422,'1bec9cca2ec689b1e80245b84f2b53c9441d1aa6daccf2ceb27490768bffa95954fa585bd275def31069d874d543d9ba9e6591fe9ade2dbd9f34ec5c0fd0050c')}
FEATURES=['CX16','LAHF_SAHF','POPCNT','SSE3','SSSE3','SSE4_1','SSE4_2']
class Denied(ValueError):pass
def need(v,why):
 if not v:raise Denied(why)
def canonical(v):return json.dumps(v,sort_keys=True,separators=(',',':'),ensure_ascii=False).encode()
def h(v):return hashlib.sha256(canonical(v)).hexdigest()
def schema_check(v,s,path='$'):
 if 'const' in s:need(v==s['const'] and (not (isinstance(v,bool) or isinstance(s['const'],bool)) or type(v) is type(s['const'])),'FACT_SCHEMA_CONST:'+path)
 if 'enum' in s:need(v in s['enum'],'FACT_SCHEMA_ENUM:'+path)
 if 'type' in s:
  types=s['type'] if isinstance(s['type'],list) else [s['type']];ok=any((t=='object' and type(v) is dict) or (t=='array' and type(v) is list) or (t=='string' and type(v) is str) or (t=='integer' and type(v) is int) or (t=='number' and type(v) in (int,float)) or (t=='boolean' and type(v) is bool) or (t=='null' and v is None) for t in types);need(ok,'FACT_SCHEMA_TYPE:'+path)
 if type(v) is dict:
  props=s.get('properties',{});need(all(k in v for k in s.get('required',[])),'FACT_SCHEMA_REQUIRED:'+path)
  if s.get('additionalProperties') is False:need(set(v)<=set(props),'FACT_SCHEMA_EXTRA:'+path)
  for k,value in v.items():
   if k in props:schema_check(value,props[k],path+'.'+k)
 if type(v) is list:
  need(len(v)>=s.get('minItems',0) and len(v)<=s.get('maxItems',100000),'FACT_SCHEMA_ARRAY:'+path)
  prefix=s.get('prefixItems',[])
  for i,x in enumerate(v):
   if i<len(prefix):schema_check(x,prefix[i],path+'['+str(i)+']')
   else:
    item=s.get('items',{});need(item is not False,'FACT_SCHEMA_ARRAY_EXTRA:'+path)
    if isinstance(item,dict):schema_check(x,item,path+'[]')
 if type(v) is str:
  need(s.get('minLength',0)<=len(v)<=s.get('maxLength',100000),'FACT_SCHEMA_SIZE:'+path)
  if 'pattern' in s:need(re.fullmatch(s['pattern'],v) is not None,'FACT_SCHEMA_PATTERN:'+path)
 if type(v) in (int,float):need(v>=s.get('minimum',float('-inf')) and v>s.get('exclusiveMinimum',float('-inf')) and v<=s.get('maximum',float('inf')),'FACT_SCHEMA_RANGE:'+path)
def catalog(c,rid):
 need(c.get('state')=='REVIEWED_TYPED_ARCHIVE_INPUT_NOT_EXECUTED' and c.get('purpose')=='FIXED_CI_QUALIFICATION_ONLY','Q_CATALOG_STATE')
 need(c.get('rid')==rid and rid in HOSTS and c.get('sdk')=='11.0.100' and c.get('runtime')=='11.0.0','Q_CATALOG_RID')
 need(c.get('memberManifestSha256')==MANIFESTS[rid] and (c.get('url'),c.get('bytes'),c.get('sha512'))==RAW[rid],'Q_CATALOG_IDENTITY')
 need(h(c.get('members'))==MANIFESTS[rid],'Q_CATALOG_MEMBERS')
def source(actual,expected):
 need(re.fullmatch('[0-9a-f]{40}',str(expected)) is not None and actual==expected,'Q_SOURCE_IDENTITY')
# Closed documented image variant; preserve the observed ImageOS value verbatim.
# Release/source pin: actions/runner-images win25-vs2026/20261103.298;
# Windows2025-VS2026-Readme.md; no wildcard/future-image admission.
def windows_host_predicates(v):
 image=v.get('imageOS');version=v.get('imageVersion');build=v.get('kernelBuild');name=v.get('osVersion')
 return {'imageVariantDocumented':image=='win25' or (image=='win25-vs2026' and version=='20261103.298.1'),'registryKernel26100':type(build) is str and build.split('.')[0]=='26100','registryServer2025':type(name) is str and 'Windows Server 2025' in name}

def host(v,rid):
 need(v.get('hostClass')==HOSTS[rid] and v.get('rid')==rid and v.get('architecture')=='x64','Q_HOST_CLASS')
 need(v.get('imageVersion') and v.get('imageOS') and v.get('runId') and v.get('instanceId') and v.get('job')=='verify' and v.get('repository')=='pouriajamali/data-admission-gate','Q_HOST_IMAGE')
 if rid=='win-x64':need(all(windows_host_predicates(v).values()),'Q_HOST_OS')
 else:need(v.get('imageOS')=='ubuntu24' and v.get('osVersion')=='Ubuntu 24.04' and type(v.get('uid')) is int and v['uid']>0 and type(v.get('gid')) is int and v['gid']>0,'Q_HOST_OS')
def caps(v,rid):
 need(type(v) is dict and v.get('kind')==('actual-Windows-Job' if rid=='win-x64' else 'actual-Linux-cgroup-v2'),'Q_ACTUAL_CAP_REQUIRED')
 need(v.get('memoryMax')==4294967296 and v.get('tasksMax')==64 and type(v.get('effectiveCpuCores')) in (int,float) and 0<v['effectiveCpuCores']<=2,'Q_CAP_PROFILE')
 need(v.get('membershipBeforeExec') is True and v.get('heldChildIdentityBeforeExec') is True,'Q_PREEXEC_MEMBERSHIP')
 if rid=='linux-x64':need(v.get('swapMax')==0 and v.get('uid',0)>0,'Q_CAP_PROFILE')
def cpu(v):need(v.get('features')==FEATURES and v.get('processorCount',0)>0,'Q_CPU_V2_BEFORE_SDK')
def terminal(v):need(v.get('workerExitCode')==0 and v.get('ownedPopulation')==0 and v.get('supervisorObservedTerminal') is True and v.get('typedStopResult')=='success','Q_TERMINAL_REQUIRED')
def validate_fact(v,schema):
 need('ready' not in v and 'SDK_READY' not in v and 'qualified' not in v,'Q_TRANSFERABLE_READY_FORBIDDEN');schema_check(v,schema)
 rid=v['qualifiedOn']['rid'];host(v['qualifiedOn'],rid);caps(v['caps'],rid);need(v['qualifiedOn'].get('instanceId'),'Q_HOST_INSTANCE');need(v['qualifiedOn']['uid']==v['caps']['uid'] and v['qualifiedOn']['gid']==v['caps']['gid'],'Q_HOST_CAP_UID_GID');cpu(v['cpu']);terminal(v['terminal']);need(v['tree']['memberManifestSha256']==MANIFESTS[rid],'Q_FACT_TREE')
 need((v['archive']['url'],v['archive']['bytes'],v['archive']['sha512'])==RAW[rid],'Q_FACT_ARCHIVE');need(sorted(x['optimize'] for x in v['denials'])==[0,1,2],'Q_FACT_DENIAL_MODES')
 need(v['factType']==('WindowsCIServer2025RID' if rid=='win-x64' else 'LinuxCIUbuntu24RID'),'Q_FACT_KIND')
 return v
def consume(fact,admission,current,actual_fact_sha):
 need(admission.get('state')=='ADMITTED_EXACT_SUPPORTED_HOST_CLASS' and admission.get('projectId')=='04','CONSUMER_ADMISSION_REQUIRED')
 rid=current.get('rid');need(rid in HOSTS and admission.get('rid')==rid and fact.get('qualifiedOn',{}).get('rid')==rid,'CONSUMER_RID_MISMATCH')
 need(admission.get('producerFactSha256')==actual_fact_sha and re.fullmatch('[0-9a-f]{64}',actual_fact_sha or '') is not None,'CONSUMER_FACT_IDENTITY')
 need(admission.get('admittedForHostClass')==HOSTS[rid] and current.get('hostClass')==HOSTS[rid] and fact['qualifiedOn'].get('hostClass')==HOSTS[rid],'CONSUMER_HOST_CLASS_MISMATCH')
 need(admission.get('sourceCommit')==current.get('sourceCommit') and admission.get('sourceTree')==current.get('sourceTree') and admission.get('contractSha256')==current.get('contractSha256'),'CONSUMER_SOURCE_CONTRACT')
 need(admission.get('catalogManifestSha256')==MANIFESTS[rid] and fact.get('tree',{}).get('memberManifestSha256')==MANIFESTS[rid],'CONSUMER_TREE_IDENTITY')
 # qualifiedOn is immutable producerhistory. A different currentjob is expected.
 need(bool(current.get('runId')) and bool(current.get('job')) and bool(current.get('attempt')),'CONSUMER_CURRENT_EXECUTION_REQUIRED')
 caps(current.get('caps'),rid);return {'admittedForHostClass':HOSTS[rid],'producerQualifiedOn':fact['qualifiedOn'],'currentExecution':{k:current[k] for k in ('runId','job','attempt')},'producerFactSha256':actual_fact_sha,'scope':'OWN_HOST_AND_CONTRACT_ONLY_NO_AGGREGATE_READY'}
