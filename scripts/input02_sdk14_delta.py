"""Finite02 command/config and verify-report delta; called only by its own held worker.

No launcher, SDK acquisition, PKI implementation, ambient feed or product target.
Caller retains the original02 controls and must finish input admission before restore.
"""
import base64, hashlib, json, pathlib, re, time, xml.etree.ElementTree as ET

PROJECTS=('ExecutionLab','ExecutionLab.Hosting','ExecutionLab.Persistence','ExecutionLab.Api','ExecutionLab.Tests','ExecutionLab.Measurements')
OFFICIAL_REPOSITORY_CERTIFICATES=frozenset((
 '0e5f38f57dc1bcc806d8494f4f90fbcedd988b46760709cbeec6f4219aa6157d',
 '5a2901d6ada3d18260b9c6dfe2133c95d74b9eef6ae0e5dc334c8454d1477df4',
 '1f4b311d9acc115c8dc8018b5a49e00fce6da8e2855f9f014ca6f34570bc482d'))
# Exact official signing history already retained in common4dab:
# tools/sdk11-normal/native-linux/metadata/repository.json SHA256
# 5f45cbf2d7f8a4b57fea6e43bb603d29a0682058a71eb61d900db74860d210b0.
ROLE_LINES={
 'Verifying the author primary signature with certificate:',
 "Verifying author primary signature's timestamp with timestamping service certificate:",
 'Verifying the repository countersignature with certificate:',
 "Verifying repository countersignature's timestamp with timestamping service certificate:",
 'Verifying the repository primary signature with certificate:',
 "Verifying repository primary signature's timestamp with timestamping service certificate:"}

def need(value,code):
    if not value:raise ValueError(code)

def verification_report(stdout,stderr,rows,exit_code):
    """Normalized hashes come only from successful official SDK verify output.

    This report is not the separate current-PKI/advisory/notices admission.
    Reused03 successful reports stay separate and are not replayed in this batch.
    """
    need(type(stdout) is bytes and type(stderr) is bytes and not stderr and exit_code==0,'VERIFY_EXIT_OR_STDERR')
    need(0<len(rows)<=64 and len(stdout)<=min(1048576,len(rows)*32768),'VERIFY_FINITE_LOG_BOUND')
    text=stdout.decode('utf-8',errors='strict')
    need(not any(ord(c)<32 and c not in '\r\n\t' for c in text),'VERIFY_LOG_CONTROL')
    lines=[x.strip() for x in text.splitlines()]
    need(not any(re.search(r'\b(?:error|warning)\b|\bNU\d{4}\b|validation failed|verification failed|(?:revocation|chain|timestamp).*?(?:unknown|invalid|unavailable)|(?:unknown|invalid).*?(?:revocation|chain|timestamp)',x,re.I) for x in lines),'VERIFY_ISSUE_REQUIRES_HOLD')
    starts=[i for i,x in enumerate(lines) if x.startswith('Verifying ') and x not in ROLE_LINES]
    need(len(starts)==len(rows),'VERIFY_EXACT_BATCH_COUNT')
    need(not any(x.startswith(('Content hash','Successfully verified package')) for x in lines[:starts[0]]),'VERIFY_UNBOUND_PREAMBLE')
    keys=set();out=[]
    for i,row in enumerate(rows):
        need(type(row) is dict and re.fullmatch(r'[A-Za-z0-9_.-]{1,128}',row.get('id','')) and re.fullmatch(r'[0-9A-Za-z.+-]{1,64}',row.get('version','')),'VERIFY_RAW_IDENTITY')
        key=(row['id'].casefold(),row['version']);need(key not in keys,'VERIFY_DUPLICATE_EXPECTED');keys.add(key)
        need(re.fullmatch('[0-9a-f]{64}',row.get('sha256','')) is not None,'VERIFY_RAW_SHA256_BINDING')
        identity=row['id']+'.'+row['version'];block=lines[starts[i]:starts[i+1] if i+1<len(starts) else len(lines)]
        hashes=[(n,x) for n,x in enumerate(block) if x.startswith('Content hash')];successes=[(n,x) for n,x in enumerate(block) if x.startswith('Successfully verified package')]
        need(block[0].casefold()==('Verifying '+identity).casefold() and len(hashes)==len(successes)==1,'VERIFY_EXACT_IDENTITY_HASH_SUCCESS')
        h,hline=hashes[0];s,sline=successes[0];need(0<h<s and sline.casefold()==("Successfully verified package '"+identity+"'.").casefold(),'VERIFY_IDENTITY_ORDER')
        match=re.fullmatch(r'Content hash: ([A-Za-z0-9+/]{86}==)',hline);need(match is not None,'VERIFY_CONTENT_HASH_SCHEMA');value=match.group(1)
        decoded=base64.b64decode(value,validate=True);need(len(decoded)==64 and base64.b64encode(decoded).decode()==value,'VERIFY_CANONICAL_CONTENT_HASH')
        expected=row.get('expectedNormalizedContentHash')
        if expected is not None:need(value==expected,'VERIFY_EXPECTED_NORMALIZED_HASH')
        need(any(x in ('Signature type: Author','Signature type: Repository') for x in block) and any(x.startswith('SHA256 hash: ') for x in block),'VERIFY_SIGNATURE_REPORT_REQUIRED')
        rawblock='\n'.join(block).encode();out.append({'id':row['id'],'version':row['version'],'rawSHA256':row['sha256'],'normalizedNuGetContentHash':value,'officialBatchExit':0,'reportBlockSHA256':hashlib.sha256(rawblock).hexdigest(),'currentPKI':'REQUIRES_SEPARATE_IDENTITY_BOUND_COVERAGE','inputAdmission':False})
    return out

def config_bytes(feed,cache,audit_port,repository_certificates):
    feed=pathlib.Path(feed);cache=pathlib.Path(cache)
    need(feed.is_absolute() and cache.is_absolute() and type(audit_port) is int and 1024<=audit_port<=65535,'OWN_PRIVATE_CONFIG_PATHS_PORT')
    need(0<len(repository_certificates)<=3 and len(set(repository_certificates))==len(repository_certificates) and set(repository_certificates)<=OFFICIAL_REPOSITORY_CERTIFICATES,'OFFICIAL_REPOSITORY_CERTIFICATE_SET')
    e=ET.Element('configuration');s=ET.SubElement(e,'config');ET.SubElement(s,'add',key='signatureValidationMode',value='require');ET.SubElement(s,'add',key='globalPackagesFolder',value=str(cache))
    s=ET.SubElement(e,'packageSources');ET.SubElement(s,'clear');ET.SubElement(s,'add',key='own-enumerated-originals',value=str(feed))
    ET.SubElement(ET.SubElement(e,'fallbackPackageFolders'),'clear')
    s=ET.SubElement(e,'auditSources');ET.SubElement(s,'clear');ET.SubElement(s,'add',key='own-current-snapshot',value='http://127.0.0.1:'+str(audit_port)+'/v3/index.json',allowInsecureConnections='true')
    s=ET.SubElement(e,'trustedSigners');ET.SubElement(s,'clear');r=ET.SubElement(s,'repository',name='nuget.org',serviceIndex='https://api.nuget.org/v3/index.json')
    for value in repository_certificates:ET.SubElement(r,'certificate',fingerprint=value,hashAlgorithm='SHA256',allowUntrustedRoot='false')
    return ET.tostring(e,encoding='utf-8',xml_declaration=True)

def command_plan(dotnet,checkout,private,raw_paths):
    """Resolve paths inside the existing bound02 worker; never invoke a command."""
    dotnet=pathlib.Path(dotnet);checkout=pathlib.Path(checkout);private=pathlib.Path(private)
    need(dotnet.is_absolute() and checkout.is_absolute() and private.is_absolute(),'OWN_RESOLVED_ABSOLUTE_PATHS')
    need(0<len(raw_paths)<=64 and len({str(x).casefold() for x in raw_paths})==len(raw_paths),'EXPLICIT_NEW_VERIFY_SUBSET')
    for value in raw_paths:
        path=pathlib.Path(value);need(path.is_absolute() and path.parent==private/'raw' and '..' not in path.parts and re.fullmatch(r'[A-Za-z0-9_.-]+\.nupkg',path.name) is not None and not any(ord(x)<32 for x in str(path)),'FINITE_LITERAL_RAW_PATH')
    config=private/'nuget.inputs.config';commands=[]
    for project in PROJECTS:
        commands.append({'id':'graph-'+project,'maximumSeconds':8,'argv':[str(dotnet),'msbuild',str(checkout/project/(project+'.csproj')),'-t:GenerateRestoreGraphFile','-p:RestoreGraphOutputPath='+str(private/'graphs'/(project+'.dgspec.json')),'-p:RestoreConfigFile='+str(config),'-p:TargetFramework=net11.0','-p:UseAppHost=false','-p:SelfContained=false','-p:EnableRuntimePackDownload=false','-p:DisableTransitiveFrameworkReferenceDownloads=true']})
    commands.append({'id':'verify-new-enumerated-originals','maximumSeconds':30,'argv':[str(dotnet),'nuget','verify','--all','--verbosity','detailed','--configfile',str(config),*map(str,raw_paths)],'reuseRule':'Do not include already valid identity-bound03 verifications; their exact raw/normalized/report proofs form the separately checked reused set.'})
    for project in PROJECTS:
        commands.append({'id':'lock-'+project,'maximumSeconds':28,'requires':'FULL_ENUMERATED_FEED_ADMITTED_CURRENT_GUARDS','argv':[str(dotnet),'restore',str(checkout/project/(project+'.csproj')),'--use-lock-file','--configfile',str(config),'--source',str(private/'raw'),'-warnaserror','-p:NuGetAudit=true','-p:NuGetAuditMode=all','-p:EnableRuntimePackDownload=false','-p:DisableTransitiveFrameworkReferenceDownloads=true']})
    commands.append({'id':'all-direct-transitive-audit','maximumSeconds':24,'argv':[str(dotnet),'package','list','--project',str(checkout/'ExecutionLab.Tests/ExecutionLab.Tests.csproj'),'--vulnerable','--include-transitive','--no-restore','--format','json','--output-version','1']})
    need(len(commands)==14 and sum(x['maximumSeconds'] for x in commands)+30==300,'EXACT_SDK14_ORIGINAL300')
    return {'SDKCommandsMax':14,'SDKCommandCeilingsSumSeconds':270,'dataAndTerminalSeconds':30,'curationSubbudgetSeconds':300,'jobSeconds':720,'controllerSeconds':620,'workStopSeconds':600,'commands':commands,'configPath':str(config),'SDKExecuted':0,'inputAdmission':False}

def remaining_curation(start_ns,now_ns,curation_start_ns):
    need(type(start_ns) is int and start_ns<=curation_start_ns<=now_ns<start_ns+600*10**9,'ORIGINAL02_WORK_CLOCK')
    need(curation_start_ns+300*10**9<=start_ns+600*10**9,'ORIGINAL02_CURATION_HEADROOM')
    return min(start_ns+600*10**9,curation_start_ns+300*10**9)-now_ns
