"""Project02 fixed local stages. Invoke only as the admitted launcher's child."""
import argparse
import hashlib
import importlib.util
import json
import os
from pathlib import Path
import subprocess
import sys

ROOT = Path(__file__).resolve().parents[1]
PROJECTS = ["ExecutionLab", "ExecutionLab.Hosting", "ExecutionLab.Persistence",
            "ExecutionLab.Api", "ExecutionLab.Tests", "ExecutionLab.Measurements"]

def need(value, reason):
    if not value:
        raise RuntimeError(reason)

def digest(path):
    with Path(path).open("rb") as stream:
        return hashlib.file_digest(stream, "sha256").hexdigest()

def main():
    p = argparse.ArgumentParser()
    for name in ("phase", "binding", "binding-sha256", "work"):
        p.add_argument("--" + name, required=True)
    a = p.parse_args()
    need(digest(a.binding) == a.binding_sha256, "manager binding mismatch")
    b = json.loads(Path(a.binding).read_text(encoding="utf-8-sig"))
    work = Path(a.work).resolve()
    need(work.is_relative_to(ROOT / "artifacts/tech-refresh") or (a.phase=="ci-all" and work.is_relative_to(Path(os.environ["RUNNER_TEMP"]).resolve())), "private work path")
    if a.phase == "ci-all":
        return ci_products(a,b,work)
    control = json.loads((work / "containment.json").read_text())
    need(control["child"]["pid"] == os.getpid() and control["child"]["suspendedMember"]
         and control["bindingSha256"] == a.binding_sha256
         and control["launcherSha256"] == b["launcherSha256"], "pre-resume containment receipt")
    if os.name == "nt":
        import ctypes as c
        from ctypes import wintypes as w
        k = c.WinDLL("kernel32", use_last_error=True)
        k.GetCurrentProcess.restype = w.HANDLE
        k.IsProcessInJob.argtypes = [w.HANDLE, w.HANDLE, c.c_void_p]
        member = w.BOOL()
        need(k.IsProcessInJob(k.GetCurrentProcess(), None, c.byref(member)) and member.value, "child outside Job")
    else:
        need(Path("/proc/self/cgroup").read_text().strip() == "0::" + b["cgroup"] and os.getuid() == b["uid"] == 1000, "child cgroup/UID")
    for row in b["tools"].values():
        need(Path(row["path"]).is_file() and digest(row["path"]) == row["sha256"], "tool identity mismatch")
    def tool(name):
        return b["tools"][name]["path"]
    def run(command, output=None):
        if output:
            with output.open("xb") as log:
                subprocess.run(command, cwd=ROOT, check=True, timeout=180, stdout=log)
            need(output.stat().st_size <= 1048576, "audit receipt cap")
        else:
            subprocess.run(command, cwd=ROOT, check=True, timeout=180)
    dotnet = b["dotnet"]
    locks = [ROOT / x / "packages.lock.json" for x in PROJECTS]
    if a.phase in ("csharp", "package"):
        verified = json.loads((ROOT / "artifacts/tech-refresh/audit-admission.json").read_text())
        need(verified["sdkBinding"] == a.binding_sha256 and digest(verified["audit"]) == verified["auditSha256"]
             and verified["locks"] == {str(x.relative_to(ROOT)): digest(x) for x in locks}, "fresh audit/lock identity required")
    if a.phase == "restoreAudit":
        run([sys.executable, "-I", "-B", str(ROOT / "scripts/check_tech_refresh.py"),
             "--binding", a.binding, "--binding-sha256", a.binding_sha256, "--work", str(work)])
        need(not any(x.exists() for x in locks), "lock transition already started; diagnose retained state before retry")
        for project in PROJECTS:
            run([dotnet, "restore", f"{project}/{project}.csproj", "--use-lock-file", "--source", "https://api.nuget.org/v3/index.json", "-warnaserror",
                 "-p:NuGetAudit=true", "-p:NuGetAuditMode=all", "-p:EnableRuntimePackDownload=false",
                 "-p:DisableTransitiveFrameworkReferenceDownloads=true"])
        audit = work / "audit.json"
        run([dotnet, "list", "ExecutionLab.Tests/ExecutionLab.Tests.csproj", "package",
             "--vulnerable", "--include-transitive", "--format", "json"], audit)
        report = json.loads(audit.read_text(encoding="utf-8-sig"))
        def clean(value):
            if isinstance(value, dict):
                return all(not (k in ("vulnerabilities", "errors", "problems", "warnings") and v)
                           and clean(v) for k, v in value.items())
            return all(clean(v) for v in value) if isinstance(value, list) else True
        need(report.get("projects") and report.get("sources") == ["https://api.nuget.org/v3/index.json"] and clean(report), "audit unavailable/advisory/coverage")
        need(all(x.is_file() for x in locks) and sum(x.stat().st_size for x in locks) <= 1048576, "six lock output bounds")
        with (ROOT / "artifacts/tech-refresh/audit-admission.json").open("x") as receipt:
            json.dump({"sdkBinding": a.binding_sha256, "audit": str(audit), "auditSha256": digest(audit),
                       "locks": {str(x.relative_to(ROOT)): digest(x) for x in locks}}, receipt)
    elif a.phase == "csharp":
        need(all(x.is_file() for x in locks), "real locks required")
        run([dotnet, "run", "--project", "ExecutionLab.Tests/ExecutionLab.Tests.csproj",
             "--configuration", "Release", "--no-restore"])
    elif a.phase == "frontend":
        npm = [tool("node"), tool("npmCli"), "--prefix", "OperatorPanel"]
        for action in (["ci"], ["test"], ["run", "build"]):
            run(npm + action)
    elif a.phase == "launcher":
        run([sys.executable, "-I", "-B", str(ROOT / "scripts/check_launcher.py"), "--work", str(work / "launcher")])
    elif a.phase in ("package", "extracted"):
        commit = subprocess.check_output([tool("git"), "rev-parse", "HEAD"], cwd=ROOT, text=True, timeout=10).strip()
        rid = "win-x64" if os.name == "nt" else "linux-x64"
        if a.phase == "package":
            need(not subprocess.check_output([tool("git"), "status", "--porcelain"], cwd=ROOT, timeout=10), "signed clean source required before packaging")
            run([sys.executable, "-I", "-B", str(ROOT / "scripts/package_panel.py"), "--work", str(work / "build"),
                 "--out", str(work / "delivery"), "--rid", rid, "--commit", commit, "--dotnet", dotnet])
            built = json.loads((work / "build/archive.json").read_text())
            need(built["sourceCommit"] == commit and built["rid"] == rid and digest(built["archive"]) == built["sha256"], "produced archive proof")
            with (ROOT / "artifacts/tech-refresh/package-admission.json").open("w") as receipt:
                json.dump({"path": built["archive"], "sha256": built["sha256"], "commit": commit, "sdkBinding": a.binding_sha256}, receipt)
        else:
            package = json.loads((ROOT / "artifacts/tech-refresh/package-admission.json").read_text())
            need(package["sdkBinding"] == a.binding_sha256, "archive consumer binding")
            need(digest(package["path"]) == package["sha256"] and package["commit"] == commit, "actual tested archive identity")
            spec = importlib.util.spec_from_file_location("releasecheck", ROOT / "scripts/check_release.py")
            checker = importlib.util.module_from_spec(spec)
            spec.loader.exec_module(checker)
            checker.inspect_archive(Path(package["path"]), commit, "0.6.0-preview.1", rid)
            import tarfile
            import zipfile
            destination = work / "extracted package"
            destination.mkdir()
            if rid == "win-x64":
                with zipfile.ZipFile(package["path"]) as archive:
                    archive.extractall(destination)
            else:
                with tarfile.open(package["path"]) as archive:
                    archive.extractall(destination, filter="data")
            children = list(destination.iterdir())
            need(len(children) == 1 and children[0].is_dir(), "one extracted package")
            run([sys.executable, "-I", "-B", str(ROOT / "scripts/check_package.py"),
                 "--package", str(children[0]), "--work", str(work / "runtime probe with spaces"), "--commit", commit, "--dotnet", dotnet])
    else:
        raise RuntimeError("fixed phase only")


def ci_products(args, wrapper_binding, work, normal=None):
    """Own main service worker; shared transport remains data only."""
    root = ROOT
    policy = json.loads(Path(wrapper_binding["policyPath"]).read_text())
    need(digest(wrapper_binding["policyPath"]) == wrapper_binding["policySha256"], "policy identity")
    context = wrapper_binding["current"]
    control = json.loads((work/"containment.json").read_text())
    need(control["child"]["pid"] == os.getpid() and control["child"]["suspendedMember"]
         and control["currentJob"] == context["job"], "current controlled child")
    if os.name != "nt":
        need(os.getuid() == context["uid"] > 0 and os.getgid() == context["gid"] > 0, "nonroot consumer")
    interface = policy["producerInterface"]
    need(interface["sha256"] == "63e04fa5d270c87b93e6e1f4c38bfbcf336b950b39fe1854dc4e514f0661f14c" and digest(interface["path"]) == interface["sha256"], "canonical04 schema source pin")
    fact_ref = policy["producerFact"]
    need(digest(fact_ref["path"]) == fact_ref["sha256"], "accepted fact digest")
    fact = json.loads(Path(fact_ref["path"]).read_text())
    spec = importlib.util.spec_from_file_location("ci_guard", root/"scripts/check_tech_refresh.py")
    guard = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(guard)
    own = {"currentJob":context["job"],"rid":context["rid"],"caps":control["caps"],
           "heldBeforeResume":control["child"]["suspendedMember"],"controllerSha256":control["launcherSha256"],
           "uid":getattr(os,"getuid",lambda:None)(),"gid":getattr(os,"getgid",lambda:None)(),
           "capsEvidenceSha256":digest(work/"own-caps.json"),
           "sourcePinTableSha256":hashlib.sha256(json.dumps(json.loads(Path(policy["sourcePinTable"]["path"]).read_text())["sourcePins"],sort_keys=True,separators=(",",":"),ensure_ascii=False).encode()).hexdigest(),
           "profileSha256":digest(policy["profile"]["path"])}
    handshake = guard.supported_ci_handshake(policy,fact,context,own)
    locks = [root/p/"packages.lock.json" for p in PROJECTS]
    need(all(p.is_file() for p in locks), "committed six locks required; no hidden CI lock transition")
    need(context["rid"] == "linux-x64" and normal is not None, "normal Windows denied; own main worker context required")
    transport, call_context, sdk_directory = normal
    sdk_root, sdk_receipt = transport.transport(context["rid"], sdk_directory, call_context)
    need(sdk_receipt["memberManifestSha256"] == fact["tree"]["memberManifestSha256"]
         and sdk_receipt["producerFactSha256"] == fact_ref["sha256"]
         and sdk_receipt["SDKExecutions"] == 0, "exact data-only normal receipt")
    dotnet = sdk_root / "dotnet"
    need(dotnet.resolve().is_relative_to(Path(sdk_directory).resolve()), "exact private SDK entry")
    with (work/"normal-input.json").open("x") as receipt:
        json.dump(sdk_receipt, receipt)
    for row in policy["tools"].values():
        need(digest(row["path"]) == row["sha256"], "preinstalled tool identity; never install/fallback")
    os.environ["DOTNET_ROOT"] = str(sdk_root)
    os.environ["DOTNET_MULTILEVEL_LOOKUP"] = "0"
    os.environ["PATH"] = os.pathsep.join(policy["toolDirectories"])
    def run(argv):
        subprocess.run([str(x) for x in argv],cwd=root,check=True,timeout=180)
    for project in PROJECTS:
        run([dotnet,"restore",f"{project}/{project}.csproj","--locked-mode","--source","https://api.nuget.org/v3/index.json","-warnaserror","-p:NuGetAudit=true","-p:NuGetAuditMode=all"])
    audit = work/"audit.json"
    with audit.open("xb") as stream:
        subprocess.run([str(dotnet),"list","ExecutionLab.Tests/ExecutionLab.Tests.csproj","package","--vulnerable","--include-transitive","--format","json"],
                       cwd=root,stdout=stream,check=True,timeout=90)
    report = json.loads(audit.read_text())
    def clean(v):
        return all(not(k in ("vulnerabilities","errors","problems","warnings") and x) and clean(x) for k,x in v.items()) if isinstance(v,dict) else all(clean(x) for x in v) if isinstance(v,list) else True
    need(audit.stat().st_size <= 1048576 and report.get("projects") and report.get("sources") == ["https://api.nuget.org/v3/index.json"] and clean(report), "fresh applicable audit")
    npm = [policy["tools"]["node"]["path"],policy["tools"]["npmCli"]["path"],"--prefix","OperatorPanel"]
    run(npm+["ci"])
    run(npm+["test"])
    run([dotnet,"run","--project","ExecutionLab.Tests/ExecutionLab.Tests.csproj","-c","Release","--no-restore"])
    run([dotnet,"build","ExecutionLab.Measurements/ExecutionLab.Measurements.csproj","-c","Release","--no-restore"])
    run([sys.executable,"-I","-B","scripts/check_launcher.py","--work","artifacts/launcher"])
    run([sys.executable,"-I","-B","scripts/package_panel.py","--work","artifacts/build","--out","artifacts/delivery",
         "--rid",context["rid"],"--commit",context["source"]["commit"],"--dotnet",dotnet])
    archive = json.loads((root/"artifacts/build/archive.json").read_text())
    need(digest(archive["archive"]) == archive["sha256"], "actual archive")
    spec = importlib.util.spec_from_file_location("checker",root/"scripts/check_release.py")
    checker = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(checker)
    checker.inspect_archive(Path(archive["archive"]),context["source"]["commit"],"0.6.0-preview.1",context["rid"])
    destination = root/"artifacts/extracted package"
    destination.mkdir()
    if context["rid"] == "win-x64":
        import zipfile
        with zipfile.ZipFile(archive["archive"]) as source:
            source.extractall(destination)
    else:
        import tarfile
        with tarfile.open(archive["archive"]) as source:
            source.extractall(destination,filter="data")
    children = list(destination.iterdir())
    need(len(children)==1 and children[0].is_dir(),"one package")
    run([sys.executable,"-I","-B","scripts/check_package.py","--package",children[0],
         "--work","artifacts/runtime probe with spaces","--commit",context["source"]["commit"],"--dotnet",dotnet])
    need(transport.inspect_sdk(context["rid"], sdk_root, call_context)["state"] == "OWN_CURRENT_FULL_INPUT_IDENTITY_VERIFIED", "post-use immutable SDK tree")
    (work/"host-handshake.json").write_text(json.dumps(handshake)+"\n")

if __name__ == "__main__":
    main()
