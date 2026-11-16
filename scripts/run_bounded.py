"""Project02 fixed-phase launcher. Source only until manager input/control admission.
No SDK bootstrap, shell passthrough, cgroup/service repair or foreign lease reset.
"""
import argparse
import hashlib
import json
import os
from pathlib import Path
import signal
import subprocess
import sys
import time
import uuid

BASE = "a197398c317256bf8ad0cbb5348a1cf0673e82aa"
M0 = "58e787ccf3e9e65b063d8bccd76d2b8332f106b9d4268cf66644a7af32f22a83"
APPROVAL = "142dac81ae7f6e05f52319d3521d4825d5df028e37542b7623d16316ff7dd077"
PROTOCOL = "9120ca49a0d46673053aa0ec0cdbbc6f00731d71ea0b57ddab09e8fc3ac3ac8b"
ROOT = Path(__file__).resolve().parents[1]
WINROOT = "E:/Codex WorkSpace/Git Projects/trading-execution-lab/workspace-local/tech-refresh-net11-20261114/repo"
LINROOT = "/home/ubuntu/execution02-net11-20261114/repo"
MANAGER = ("E:/Codex WorkSpace/Git Projects/" if os.name == "nt" else "/mnt/e/Codex WorkSpace/Git Projects/") + "portfolio-management/development-management-20261110/wave2-state/"
CAPS = {"memoryBytes": 4294967296, "cpuCores": 2, "tasks": 64, "swapBytesLinux": 0,
        "workspaceBytes": 8589934592, "logBytes": 33554432, "receiptBytes": 1048576}
PHASES = {"probe": 120, "restoreAudit": 300, "csharp": 480, "frontend": 180,
          "launcher": 120, "package": 480, "extracted": 180}

class Hold(RuntimeError):
    pass

def require(condition, message):
    if not condition:
        raise Hold(message)

def sha(path):
    with Path(path).open("rb") as stream:
        return hashlib.file_digest(stream, "sha256").hexdigest()

def load(path, expected=None):
    p = Path(path)
    require(p.is_file() and not p.is_symlink() and p.stat().st_size <= CAPS["receiptBytes"], "receipt path/type/size")
    require(expected is None or sha(p) == expected, "receipt digest mismatch")
    return json.loads(p.read_text(encoding="utf-8-sig"))

def save(path, value):
    raw = (json.dumps(value, indent=2) + "\n").encode()
    require(len(raw) <= CAPS["receiptBytes"], "receipt cap")
    with Path(path).open("xb") as stream:
        stream.write(raw)
        stream.flush()
        os.fsync(stream.fileno())

def safe_path(path, root):
    p, r = Path(path).absolute(), Path(root).resolve()
    require(p.is_relative_to(r), "path escape")
    for item in [p, *p.parents]:
        require(not item.is_symlink() and not item.is_junction(), "link/reparse path")
        if item == r:
            break
    return p

def footprint(log_root=None, workspace=ROOT):
    total = logs = 0
    for base, dirs, files in os.walk(workspace, followlinks=False):
        for name in [*dirs, *files]:
            p = Path(base) / name
            require(not p.is_symlink() and not p.is_junction(), "workspace link")
        for name in files:
            p = Path(base) / name
            try:
                size = p.stat().st_size
            except FileNotFoundError:
                continue
            total += size
            if log_root is not None and p.is_relative_to(log_root) and p.suffix in (".log", ".jsonl"):
                logs += size
            require(total <= CAPS["workspaceBytes"], "workspace size exceeded")
    return total, logs

def binding(args):
    admitted_at = time.monotonic()
    b = load(args.binding, args.binding_sha256)
    require(b["schema"] == "execution02-native-binding/v1" and b["project"] == "02", "wrong project/schema")
    require(b["rid"] == ("win-x64" if os.name == "nt" else "linux-x64"), "RID mismatch")
    require(b["contractSha256"] == M0 and b["approvalSha256"] == APPROVAL and b["baseCommit"] == BASE, "authority identity")
    require(b["caps"] == CAPS and b["phaseDeadlines"] == PHASES, "fixed profile mismatch")
    require(ROOT == Path(WINROOT if os.name == "nt" else LINROOT).resolve()
            and ROOT == Path(b["checkout"]).resolve(), "wrong private checkout")
    safe_path(ROOT, ROOT.anchor)
    require((ROOT / ".git/HEAD").read_text().strip() == "ref: refs/heads/codex/project02-net11-20261114", "wrong branch")
    require(sha(Path(__file__)) == b["launcherSha256"], "launcher identity")
    require(sha(Path(MANAGER) / "LEASE-PROTOCOL.json") == PROTOCOL, "canonical protocol changed")
    require(1 <= len(b["sourceFiles"]) <= 160, "source inventory bounds")
    names = {row["path"] for row in b["sourceFiles"]}
    require(len(names) == len(b["sourceFiles"]) and {"scripts/run_bounded.py", "scripts/qualify_tech_refresh.py", "global.json", "Directory.Build.props"} <= names, "incomplete/duplicate source inventory")
    for row in b["sourceFiles"]:
        p = safe_path(ROOT / row["path"], ROOT)
        require(p.is_file() and p.stat().st_size == row["bytes"] and sha(p) == row["sha256"], "source input mismatch")
    require(sha(sys.executable) == b["pythonSha256"], "bootstrap interpreter identity")
    require(os.name == "nt", "local Linux R3 STOP; supported CI only")
    require(args.phase == "probe" and b["mode"] == "CONTROL_PROBE_ONLY", "local SDK targets excluded; supported CI route required")
    require(time.monotonic() - admitted_at <= 120, "input guard deadline")
    return b

class Linux:
    def __init__(self, b):
        require(os.getuid() == b["uid"] > 0 and os.getgid() == b["gid"] > 0 and os.uname().machine == "x86_64", "actual nonroot runner UID/GID")
        self.path = Path("/sys/fs/cgroup" + b["cgroup"])
        require(self.path.resolve().is_relative_to(Path("/sys/fs/cgroup")) and self.path != Path("/sys/fs/cgroup"), "cgroup path")
        require(Path("/proc/self/cgroup").read_text().strip() == "0::" + b["cgroup"], "wrapper not in admitted cgroup")
        self.owner_start = Path("/proc/self/stat").read_text().rsplit(")", 1)[1].split()[19]
        self.owned = set()
        self.readback = self.inspect()
        require(b["exclusiveCgroup"] is True and self.members() == {os.getpid()}, "cgroup not dedicated to this owner")
        self.pid = None
        self.code = None

    def members(self):
        return {int(p) for p in (self.path / "cgroup.procs").read_text().split()}

    def inspect(self):
        values = {n: (self.path / n).read_text().strip() for n in ("memory.max", "memory.swap.max", "cpu.max", "pids.max")}
        quota, period = values["cpu.max"].split()
        require(int(values["memory.max"]) == CAPS["memoryBytes"] and values["memory.swap.max"] == "0"
                and values["pids.max"] == "64" and quota != "max" and 0 < int(quota) <= 2 * int(period), "kernel cap mismatch")
        return values

    def start(self, command, env, log):
        self.pid = os.fork()
        if self.pid == 0:
            try:
                os.setsid()
                os.dup2(log.fileno(), 1)
                os.dup2(log.fileno(), 2)
                os.chdir(ROOT)
                with open(os.devnull, "rb") as null:
                    os.dup2(null.fileno(), 0)
                os.kill(os.getpid(), signal.SIGSTOP)
                os.execve(command[0], command, env)
            except BaseException:
                os._exit(126)
        deadline = time.monotonic() + 5
        while time.monotonic() < deadline:
            pid, status = os.waitpid(self.pid, os.WUNTRACED | os.WNOHANG)
            if pid:
                if not os.WIFSTOPPED(status):
                    self.code = os.waitstatus_to_exitcode(status)
                    raise Hold("child exited before containment")
                break
            time.sleep(.02)
        else:
            raise Hold("suspended child deadline")
        require(self.inspect() == self.readback and self.pid in self.members(), "child cgroup not contained")
        self.child = {"pid": self.pid, "start": Path(f"/proc/{self.pid}/stat").read_text().rsplit(")", 1)[1].split()[19],
                      "suspendedMember": True}

    def resume(self):
        os.kill(self.pid, signal.SIGCONT)

    def poll(self):
        if self.code is None:
            pid, status = os.waitpid(self.pid, os.WNOHANG)
            if pid:
                self.code = os.waitstatus_to_exitcode(status)
        return self.code

    def capture_owned(self):
        for pid in self.members() - {os.getpid()}:
            try:
                stat = Path(f"/proc/{pid}/stat").read_text().rsplit(")", 1)[1].split()
                identity = (pid, stat[19])
                cursor = pid
                for _ in range(64):
                    if cursor == os.getpid():
                        self.owned.add(identity)
                        break
                    if cursor <= 1:
                        break
                    cursor = int(Path(f"/proc/{cursor}/stat").read_text().rsplit(")", 1)[1].split()[1])
                require(identity in self.owned, "unidentified cgroup process; no foreign termination")
            except FileNotFoundError:
                continue

    def finish(self):
        # Dedicated manager-admitted cgroup only; never signal a foreign cgroup/unit.
        deadline = time.monotonic() + 5
        while time.monotonic() < deadline:
            self.capture_owned()
            for pid in self.members() - {os.getpid()}:
                try:
                    fd = os.pidfd_open(pid)
                    try:
                        member = Path(f"/proc/{pid}/cgroup").read_text().strip()
                        start = Path(f"/proc/{pid}/stat").read_text().rsplit(")", 1)[1].split()[19]
                        require(member == Path("/proc/self/cgroup").read_text().strip() and (pid, start) in self.owned, "changed child ownership")
                        signal.pidfd_send_signal(fd, signal.SIGKILL)
                    finally:
                        os.close(fd)
                except ProcessLookupError:
                    pass
            if self.pid and self.code is None:
                self.poll()
            if self.members() == {os.getpid()} and int((self.path / "pids.current").read_text()) == 1:
                return True
            time.sleep(.05)
        return False

def windows_class():
    import ctypes as c
    from ctypes import wintypes as w
    class Basic(c.Structure):
        _fields_ = [("processTime", c.c_int64), ("jobTime", c.c_int64), ("flags", w.DWORD),
                    ("minWS", c.c_size_t), ("maxWS", c.c_size_t), ("processes", w.DWORD),
                    ("affinity", c.c_size_t), ("priority", w.DWORD), ("scheduling", w.DWORD)]
    class Extended(c.Structure):
        _fields_ = [("basic", Basic), ("io", c.c_uint64 * 6), ("processMemory", c.c_size_t),
                    ("jobMemory", c.c_size_t), ("peakProcess", c.c_size_t), ("peakJob", c.c_size_t)]
    class Accounting(c.Structure):
        _fields_ = [("times", c.c_int64 * 4), ("faults", w.DWORD), ("total", w.DWORD),
                    ("active", w.DWORD), ("terminated", w.DWORD)]
    class Startup(c.Structure):
        _fields_ = [("cb", w.DWORD), ("reserved", w.LPWSTR), ("desktop", w.LPWSTR), ("title", w.LPWSTR),
                    ("x", w.DWORD), ("y", w.DWORD), ("xs", w.DWORD), ("ys", w.DWORD),
                    ("xc", w.DWORD), ("yc", w.DWORD), ("fill", w.DWORD), ("flags", w.DWORD),
                    ("show", w.WORD), ("reservedSize", w.WORD), ("reserved2", c.c_void_p),
                    ("stdin", w.HANDLE), ("stdout", w.HANDLE), ("stderr", w.HANDLE)]
    class Process(c.Structure):
        _fields_ = [("process", w.HANDLE), ("thread", w.HANDLE), ("pid", w.DWORD), ("tid", w.DWORD)]
    k = c.WinDLL("kernel32", use_last_error=True)
    signatures = {
        "CreateJobObjectW": ([c.c_void_p, w.LPCWSTR], w.HANDLE),
        "SetInformationJobObject": ([w.HANDLE, c.c_int, c.c_void_p, w.DWORD], w.BOOL),
        "QueryInformationJobObject": ([w.HANDLE, c.c_int, c.c_void_p, w.DWORD, c.c_void_p], w.BOOL),
        "GetCurrentProcess": ([], w.HANDLE),
        "GetProcessAffinityMask": ([w.HANDLE, c.c_void_p, c.c_void_p], w.BOOL),
        "GetProcessTimes": ([w.HANDLE, c.c_void_p, c.c_void_p, c.c_void_p, c.c_void_p], w.BOOL),
        "CreateProcessW": ([w.LPCWSTR, w.LPWSTR, c.c_void_p, c.c_void_p, w.BOOL, w.DWORD, c.c_void_p, w.LPCWSTR, c.c_void_p, c.c_void_p], w.BOOL),
        "AssignProcessToJobObject": ([w.HANDLE, w.HANDLE], w.BOOL),
        "IsProcessInJob": ([w.HANDLE, w.HANDLE, c.c_void_p], w.BOOL),
        "ResumeThread": ([w.HANDLE], w.DWORD), "WaitForSingleObject": ([w.HANDLE, w.DWORD], w.DWORD),
        "GetExitCodeProcess": ([w.HANDLE, c.c_void_p], w.BOOL),
        "TerminateJobObject": ([w.HANDLE, w.UINT], w.BOOL),
        "TerminateProcess": ([w.HANDLE, w.UINT], w.BOOL), "CloseHandle": ([w.HANDLE], w.BOOL)}
    for name, (args, result) in signatures.items():
        getattr(k, name).argtypes, getattr(k, name).restype = args, result

    class Windows:
        def __init__(self, b):
            require(c.sizeof(c.c_void_p) == 8, "x64 wrapper required")
            self.job = k.CreateJobObjectW(None, None)
            require(self.job, "create own Job failed")
            self.pi = None
            self.child = self.child_proof = None
            created, exited, kernel, user = (c.c_uint64() for _ in range(4))
            require(k.GetProcessTimes(k.GetCurrentProcess(), c.byref(created), c.byref(exited), c.byref(kernel), c.byref(user)), "wrapper start identity")
            self.owner_start = created.value
            affinity, system = c.c_size_t(), c.c_size_t()
            require(k.GetProcessAffinityMask(k.GetCurrentProcess(), c.byref(affinity), c.byref(system)), "affinity query")
            bits = [1 << i for i in range(64) if affinity.value & (1 << i)][:2]
            require(bits, "empty CPU affinity")
            self.limits = Extended()
            self.limits.basic.flags = 0x2318  # kill-on-close, job/process memory, active processes, affinity
            self.limits.basic.affinity = sum(bits)
            self.limits.basic.processes = 64
            self.limits.processMemory = self.limits.jobMemory = CAPS["memoryBytes"]
            require(k.SetInformationJobObject(self.job, 9, c.byref(self.limits), c.sizeof(self.limits)), "Job cap assignment failed")
            actual = Extended()
            require(k.QueryInformationJobObject(self.job, 9, c.byref(actual), c.sizeof(actual), None), "Job cap query")
            require(actual.basic.flags == self.limits.basic.flags and actual.basic.affinity == sum(bits)
                    and actual.basic.processes == 64 and actual.processMemory == actual.jobMemory == CAPS["memoryBytes"], "Job readback mismatch")
            self.readback = {"flags": actual.basic.flags, "affinity": actual.basic.affinity, "cpuCount": len(bits),
                             "activeProcessLimit": 64, "processMemory": actual.processMemory, "jobMemory": actual.jobMemory}

        def start(self, command, env, log):
            import msvcrt
            si, self.pi = Startup(), Process()
            si.cb, si.flags = c.sizeof(si), 0x100
            handle = msvcrt.get_osfhandle(log.fileno())
            os.set_handle_inheritable(handle, True)
            null = open(os.devnull, "rb")
            try:
                si.stdin = msvcrt.get_osfhandle(null.fileno())
                os.set_handle_inheritable(si.stdin, True)
                si.stdout = si.stderr = handle
                block = c.create_unicode_buffer("\0".join(f"{n}={v}" for n, v in sorted(env.items(), key=lambda x: x[0].upper())) + "\0\0")
                cmd = c.create_unicode_buffer(subprocess.list2cmdline(command))
                require(k.CreateProcessW(command[0], cmd, None, None, True, 0x08000404, block, str(ROOT), c.byref(si), c.byref(self.pi)), "suspended CreateProcess failed")
            finally:
                null.close()
                os.set_handle_inheritable(handle, False)
            self.child = {"pid": self.pi.pid, "start": None, "suspendedMember": False}
            created, exited, kernel, user = (c.c_uint64() for _ in range(4))
            require(k.GetProcessTimes(self.pi.process, c.byref(created), c.byref(exited), c.byref(kernel), c.byref(user)), "child start identity")
            self.child["start"] = created.value
            member = w.BOOL()
            if not (k.AssignProcessToJobObject(self.job, self.pi.process)
                    and k.IsProcessInJob(self.pi.process, self.job, c.byref(member)) and member.value):
                self.prove_child_terminal()
                raise Hold("suspended child containment failed")
            self.child["suspendedMember"] = True

        def resume(self):
            require(k.ResumeThread(self.pi.thread) != 0xffffffff, "resume failed")

        def poll(self):
            if k.WaitForSingleObject(self.pi.process, 0) == 258:
                return None
            result = w.DWORD()
            require(k.GetExitCodeProcess(self.pi.process, c.byref(result)), "exit query")
            return result.value

        def prove_child_terminal(self):
            if not (self.pi and self.pi.process):
                return True
            if self.child_proof and self.child_proof["terminal"]:
                return True  # The held process object stays signalled; retain its established proof.
            terminated = bool(k.TerminateProcess(self.pi.process, 125))
            termination_error = c.get_last_error() if not terminated else 0
            waited = k.WaitForSingleObject(self.pi.process, 5000)
            code = w.DWORD()
            queried = bool(k.GetExitCodeProcess(self.pi.process, c.byref(code)))
            created, exited, kernel, user = (c.c_uint64() for _ in range(4))
            identified = bool(k.GetProcessTimes(self.pi.process, c.byref(created), c.byref(exited), c.byref(kernel), c.byref(user)))
            same_identity = identified and (self.child or {}).get("start") in (None, created.value)
            terminal = waited == 0 and queried and same_identity  # WAIT_OBJECT_0 on the held creation handle.
            self.child_proof = {"pid": self.pi.pid, "start": created.value if identified else None,
                                "terminationSucceeded": terminated, "terminationError": termination_error,
                                "waitResult": waited, "exitQuerySucceeded": queried,
                                "exitCode": code.value if queried else None, "sameIdentity": same_identity, "terminal": terminal}
            return terminal

        def finish(self):
            require(k.TerminateJobObject(self.job, 125), "own Job termination failed")
            child_terminal = self.prove_child_terminal()
            deadline = time.monotonic() + 5
            terminal = False
            while time.monotonic() < deadline:
                info = Accounting()
                require(k.QueryInformationJobObject(self.job, 1, c.byref(info), c.sizeof(info), None), "terminal Job query")
                if info.active == 0:
                    terminal = child_terminal
                    break
                time.sleep(.05)
            for handle in ([self.pi.thread, self.pi.process] if self.pi and terminal else []):
                if handle:
                    k.CloseHandle(handle)
            k.CloseHandle(self.job)
            return terminal
    return Windows

def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--binding", required=True, type=Path)
    parser.add_argument("--binding-sha256", required=True)
    parser.add_argument("--phase", required=True, choices=PHASES)
    args = parser.parse_args()
    invocation_start = time.monotonic()
    b = binding(args)
    outroot = safe_path(ROOT / "artifacts/tech-refresh", ROOT)
    outroot.mkdir(parents=True, exist_ok=True)
    previous = [load(p) for p in outroot.glob("*/receipt.json")]
    require(all(p["terminal"] is True for p in previous), "nonterminal prior phase")
    spent = sum(p["elapsedSeconds"] for p in previous)
    require(spent < 2100, "OS local elapsed envelope exhausted")
    token = uuid.uuid4().hex
    out = outroot / token
    out.mkdir()
    start = invocation_start
    lease = {"projectId": "02", "randomToken": token, "ownerOS": os.name, "ownerPID": os.getpid(),
             "ownerProcessStartIdentity": None, "phase": args.phase, "startedAtUtc": time.time(), "receiptDirectory": str(out)}
    controller = None
    claimed = terminal = False
    code = None
    failure = None
    try:
        footprint()
        controller = windows_class()(b) if os.name == "nt" else Linux(b)
        lease["ownerProcessStartIdentity"] = controller.owner_start
        save(Path(MANAGER) / "LOCAL-FIXTURE-LEASE.json", lease)
        claimed = True
        env = {n: v for n, v in os.environ.items() if not n.upper().startswith(("DOTNET_", "COMPLUS_", "CORECLR_", "MSBUILD", "NUGET_", "EXECUTION_LAB_", "ASPNETCORE_", "KESTREL__"))}
        env.update(DOTNET_MULTILEVEL_LOOKUP="0", DOTNET_CLI_TELEMETRY_OPTOUT="1", DOTNET_NOLOGO="1",
                   DOTNET_CLI_HOME=str(ROOT / "artifacts/private-cli"), NUGET_PACKAGES=str(ROOT / "artifacts/private-nuget"),
                   NUGET_HTTP_CACHE_PATH=str(ROOT / "artifacts/private-http"), PYTHONDONTWRITEBYTECODE="1")
        temporary = ROOT / "artifacts/private-tmp"
        temporary.mkdir(exist_ok=True)
        env.update(TEMP=str(temporary), TMP=str(temporary), TMPDIR=str(temporary))
        if args.phase == "probe":
            command = [sys.executable, "-I", "-B", "-c", "import os,json;print(json.dumps({'probe':'execution02','pid':os.getpid(),'uid':getattr(os,'getuid',lambda:None)()}))"]
        else:
            env["DOTNET_ROOT"] = b["sdkRoot"]
            env["PATH"] = os.pathsep.join(b["toolDirectories"])
            command = [sys.executable, "-I", "-B", str(ROOT / "scripts/qualify_tech_refresh.py"),
                       "--phase", args.phase, "--binding", str(args.binding), "--binding-sha256", args.binding_sha256, "--work", str(out)]
        with (out / "phase.log").open("xb") as log:
            controller.start(command, env, log)
            save(out / "containment.json", {"caps": CAPS, "readback": controller.readback, "child": controller.child,
                                           "launcherSha256": sha(__file__), "bindingSha256": args.binding_sha256})
            controller.resume()
            while (code := controller.poll()) is None:
                _, logs = footprint(out)
                require(logs <= CAPS["logBytes"], "aggregate log cap exceeded")
                require(time.monotonic() - start <= min(PHASES[args.phase], 2100 - spent) - 5, "phase deadline")
                if os.name != "nt":
                    require(controller.inspect() == controller.readback, "kernel caps changed")
                    controller.capture_owned()
                time.sleep(.2)
            require(code == 0, "completed child failure")
            _, logs = footprint(out)
            require(logs <= CAPS["logBytes"], "aggregate log cap exceeded")
    except BaseException as error:
        failure = type(error).__name__ + ": " + str(error)
    finally:
        terminal = controller is None
        if controller is not None:
            try:
                terminal = controller.finish()
            except BaseException as error:
                failure = "terminal control failure: " + str(error)
        if time.monotonic() - start > min(PHASES[args.phase], 2100 - spent):
            failure = "phase/OS deadline exceeded including teardown"
        receipt = {"status": "COMPLETED" if failure is None and terminal else "FAILED_OR_INCOMPLETE",
                   "purpose": "CONTROL_PROBE" if args.phase == "probe" else "LOCAL_PHASE", "phase": args.phase,
                   "project": "02", "checkout": str(ROOT), "launcherSha256": sha(__file__), "bindingSha256": args.binding_sha256,
                   "caps": CAPS, "readback": controller.readback if controller is not None else None, "exit": code,
                   "childTerminalProof": getattr(controller, "child_proof", None), "terminal": terminal, "elapsedSeconds": time.monotonic() - start,
                   "lease": lease, "failure": failure, "ownerOS": os.name,
                   "kernelLocation": None if controller is None else (str(controller.path) if os.name != "nt" else "owned Windows Job"),
                   "containmentSha256": sha(out / "containment.json") if (out / "containment.json").exists() else None,
                   "outputEnforcement": "Memory/CPU/tasks kernel bounded; workspace/log bytes monitored and fail on observed excess, not a filesystem quota."}
        save(out / "receipt.json", receipt)
        if claimed and terminal:
            current = load(Path(MANAGER) / "LOCAL-FIXTURE-LEASE.json")
            require(current == lease, "lease owner/token/start changed; retained")
            (Path(MANAGER) / "LOCAL-FIXTURE-LEASE.json").unlink()
    print(json.dumps({"status": receipt["status"], "receipt": str(out / "receipt.json")}))
    return 0 if receipt["status"] == "COMPLETED" else 1


# Supported hosted routes are separate from historical local controls. SDK0 source proposal only.
def ci_observe(rid):
    import urllib.request
    require(os.environ.get("GITHUB_ACTIONS") == "true" and os.environ.get("RUNNER_ENVIRONMENT") == "github-hosted", "hosted CI only")
    require(not Path("/.dockerenv").exists() and not Path("/run/.containerenv").exists(), "container excluded")
    if os.name == "nt":
        import winreg
        with winreg.OpenKey(winreg.HKEY_LOCAL_MACHINE, r"SOFTWARE\Microsoft\Windows NT\CurrentVersion") as key:
            product, build, ubr, install = [winreg.QueryValueEx(key, n)[0] for n in ("ProductName", "CurrentBuildNumber", "UBR", "InstallationType")]
        require(install in ("Server", "Server Core") and "2025" in product and str(build) == "26100", "actual Server2025 required")
        host, identity = "GitHubHostedWindowsServer2025x64", f"{product}/{build}.{ubr}/{install}"
        uid = gid = None
    else:
        release = dict(line.split("=", 1) for line in Path("/etc/os-release").read_text().splitlines() if "=" in line)
        require(release.get("ID", "").strip('"') == "ubuntu" and release.get("VERSION_ID", "").strip('"') == "24.04"
                and os.uname().machine == "x86_64" and "microsoft" not in os.uname().release.lower(), "actual Ubuntu24 VM required")
        require(Path("/proc/1/comm").read_text().strip() == "systemd", "existing system manager required")
        uid, gid = os.getuid(), os.getgid()
        require(uid > 0 and gid > 0, "root consumer excluded")
        flags = [set(x.split(":", 1)[1].split()) for x in Path("/proc/cpuinfo").read_text().splitlines() if x.startswith("flags")]
        require(flags and all({"cx16","popcnt","pni","ssse3","sse4_1","sse4_2","lahf_lm"} <= f for f in flags), "own x86-64-v2")
        host, identity = "GitHubHostedUbuntu24.04x64", "ubuntu/24.04/x86_64"
    require(rid == ("win-x64" if os.name == "nt" else "linux-x64"), "host RID")
    run, attempt = os.environ["GITHUB_RUN_ID"], os.environ["GITHUB_RUN_ATTEMPT"]
    require(run.isdecimal() and attempt.isdecimal() and os.environ["GITHUB_REPOSITORY"] == "pouriajamali/trading-execution-lab", "job repository/run")
    url = f"https://api.github.com/repos/pouriajamali/trading-execution-lab/actions/runs/{run}/attempts/{attempt}/jobs?per_page=100"
    request = urllib.request.Request(url, headers={"Accept":"application/vnd.github+json","User-Agent":"execution02-ci-host","X-GitHub-Api-Version":"2022-11-28"})
    with urllib.request.urlopen(request, timeout=15) as response:
        raw = response.read(1048577)
    require(len(raw) <= 1048576, "job metadata bound")
    rows = [j for j in json.loads(raw)["jobs"] if j["name"] == f"Execution02 native ({rid})" and j["runner_name"] == os.environ["RUNNER_NAME"] and j["status"] == "in_progress"]
    require(len(rows) == 1 and "self-hosted" not in rows[0]["labels"], "actual hosted job witness")
    label = "windows-2025" if rid == "win-x64" else "ubuntu-24.04"
    require(label in rows[0]["labels"], "actual job label")
    def git(*argv):
        return subprocess.check_output(["git", *argv], cwd=ROOT, text=True, timeout=10).strip()
    source = {"commit":git("rev-parse","HEAD"),"tree":git("rev-parse","HEAD^{tree}"),"dirty":bool(git("status","--porcelain"))}
    require(source["commit"] == rows[0]["head_sha"] == os.environ["GITHUB_SHA"], "actual source SHA")
    sid = subprocess.check_output([str(Path(os.environ["SystemRoot"])/"System32/whoami.exe"),"/user","/fo","csv","/nh"],text=True,timeout=5).strip() if os.name=="nt" else None
    return {"accountSidEvidence":sid,"hostClass":host,"rid":rid,"osIdentity":identity,"imageOS":os.environ["ImageOS"],
            "imageVersion":os.environ["ImageVersion"],"instanceId":os.environ["RUNNER_NAME"],"runnerTrackingId":os.environ["RUNNER_TRACKING_ID"],"runnerEnvironment":"github-hosted","isContainer":False,
            "uid":uid,"gid":gid,"source":source,"job":{"repository":os.environ["GITHUB_REPOSITORY"],
            "runId":run,"attempt":attempt,"jobId":str(rows[0]["id"]),"jobKey":os.environ["GITHUB_JOB"],
            "runnerName":rows[0]["runner_name"]},"metadataSha256":hashlib.sha256(raw).hexdigest()}

NORMAL_PINS = {'tools/check_dotnet11.py': 'd9c690d8c82825b018c04089c279036829d3baf2534c2634bba84910c415a37d', 'tools/sdk11-normal-inputs.lock.json': '686c6c778f7841e6015fa401f3892b853df80e3341fbb5d02b27c682887c1c78', 'tools/dotnet11-host-qualification.schema.json': '63e04fa5d270c87b93e6e1f4c38bfbcf336b950b39fe1854dc4e514f0661f14c', 'tools/sdk11-normal/accepted-linux-fact.json': '757abf2d3dde65d10cd895cfc97eaeccb7fc11e8685b94ad046e6a8ec8829007', 'tools/sdk11-normal/accepted-linux-acceptance.json': '0452e1f3b4f2662d57e9b273428bb37ab0c5a733551a92394ca2a4e8b9b4ac08', 'tools/qualification_input_guard.py': '7420b08d78d3b1476be41385d179a42212a2a7e1a965a8d8ea3b67bb14da7925', 'tools/materialize_qualification_linux.py': '5f0dbb951cbe615d8c6dd9edbb63b11143cc457319bdcc9000ea9a486f660fb8', 'tools/sdk11-normal/.gitattributes': 'f2fe153ebc992e87b4c933eb9b28bcf862fccb814c3e3bbe920239ee95b34360'}

def proc_identity(pid):
    raw = Path("/proc",str(pid),"stat").read_text()
    return "proc-start:" + raw[raw.rfind(")")+2:].split()[19]

def normal_documents(policy, current, held, private, start_ns, end_ns, bootstrap, hashes, pins):
    # Pure finite binding; only an exact separately approved policy may request it.
    require(policy["state"] == "EXACT_CI_CONSUMER_ADMISSION"
            and policy["currentEvidenceBinding"] == "OWN_SUPERVISOR_BINDS_CURRENT_HELD_MAINPID_V1", "own evidence route not admitted")
    require(current["rid"] == "linux-x64" and current["source"]["dirty"] is False, "normal Linux clean source only")
    require(0 < end_ns-start_ns <= 620*10**9 and held["state"] == "T"
            and held["uid"] == current["uid"] > 0 and held["gid"] == current["gid"] > 0
            and held["mainPID"] == held["pid"] and held["membershipBeforeRelease"] is True
            and held["retainedStartHandle"] is True, "own stopped MainPID required")
    expected = {"memory.max":"4294967296","memory.swap.max":"0","pids.max":"64","cpu.max":"200000 100000"}
    require(held["kernelLimits"] == expected, "own actual kernel caps")
    require(pins["projectId"] == "02" and pins["repository"] == current["job"]["repository"], "own source table")
    admission = json.loads(json.dumps(policy["consumerAdmission"]))
    bound = admission["admittedFor"]
    table_hash = hashlib.sha256(json.dumps(pins["sourcePins"],sort_keys=True,separators=(",",":"),ensure_ascii=False).encode()).hexdigest()
    require(admission["projectId"] == "02" and admission["producerFactSha256"] == NORMAL_PINS["tools/sdk11-normal/accepted-linux-fact.json"]
            and bound["contractSha256"] == hashes["contract"] and bound["profileSha256"] == hashes["profile"]
            and bound["controllerSha256"] == hashes["controller"] and bound["sourcePinTableSha256"] == table_hash, "own frozen admission source binding")
    require(bound["hostClass"] == current["hostClass"] == "GitHubHostedUbuntu24.04x64"
            and bound["rid"] == "linux-x64" and admission["state"] == "ADMITTED_EXACT_SUPPORTED_HOST_CLASS", "own admitted host")
    caps = {"schema":"sdk11-own-current-cap-evidence/v1","projectId":"02","repository":current["job"]["repository"],
            "sourceCommit":current["source"]["commit"],"sourceTree":current["source"]["tree"],
            "profileSha256":hashes["profile"],"controllerSha256":hashes["controller"],
            "worker":{k:held[k] for k in ("pid","processStartIdentity","uid","gid","cgroup","kernelLimits")},
            "beforeExec":{k:held[k] for k in ("pid","processStartIdentity","cgroup","kernelLimits","state","membershipBeforeRelease","retainedStartHandle")},
            "supervisor":{"pid":held["supervisorPID"],"processStartIdentity":held["supervisorStartIdentity"],"deadlineMonotonicNs":end_ns},
            "rowStartedMonotonicNs":start_ns,"deadlineMonotonicNs":end_ns,"bootstrap":bootstrap}
    cap_bytes = (json.dumps(caps,indent=2)+"\n").encode()
    admission["currentExecution"] = {"runId":current["job"]["runId"],"job":current["job"]["jobKey"],
        "attempt":current["job"]["attempt"],"instanceId":current["instanceId"],"ownCapsEvidenceSha256":hashlib.sha256(cap_bytes).hexdigest()}
    ctx = {"projectId":"02","repository":current["job"]["repository"],"checkout":str(ROOT),"controller":str(Path(__file__).resolve()),
           "contract":str(ROOT/"docs/SDK11-CONSUMER-CONTRACT.json"),"profile":str(ROOT/"tools/sdk11-own-profile.json"),
           "sourcePins":str(ROOT/"tools/sdk11-own-source-pins.json"),"admission":str(private/"consumer-admission.json"),
           "capsEvidence":str(private/"own-caps.json"),"expectedSourceCommit":current["source"]["commit"],"expectedSourceTree":current["source"]["tree"],
           "rowStartedMonotonicNs":start_ns,"deadlineMonotonicNs":end_ns,"supervisorPID":held["supervisorPID"],"supervisorStartIdentity":held["supervisorStartIdentity"]}
    return caps, admission, ctx

def normal_module():
    import importlib.util
    for name, expected in NORMAL_PINS.items():
        require(sha(ROOT/name) == expected, "shared04 byte identity: " + name)
    spec = importlib.util.spec_from_file_location("execution02_shared_normal",ROOT/"tools/check_dotnet11.py")
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module

def ci_row(args):
    start_ns = int(args.ci_row_start) if args.ci_row_start else time.monotonic_ns()
    end_ns = start_ns + 620*10**9
    require(start_ns <= time.monotonic_ns() < end_ns, "original row clock")
    policy = load(args.ci_policy,args.ci_policy_sha256)
    require(policy["state"] == "EXACT_CI_CONSUMER_ADMISSION" and policy["caps"] == CAPS, "inert policy cannot execute")
    require(sha(sys.executable) == policy["pythonSha256"] and sha(__file__) == policy["controllerSha256"], "exact controller/bootstrap")
    if args.ci_worker:
        require(os.name != "nt" and args.ci_rid == "linux-x64", "normal Windows denied")
        private = args.ci_context.parent
        require(private.parent == Path(os.environ["RUNNER_TEMP"]).resolve(), "private root")
        # This process IS systemd MainPID. Supervisor observes stateT before release.
        os.kill(os.getpid(),signal.SIGSTOP)
        ctx = load(private/"normal-context.json")
        require(ctx["deadlineMonotonicNs"] == end_ns and ctx["rowStartedMonotonicNs"] == start_ns, "inherited original deadline")
        current = load(args.ci_context,args.ci_context_sha256)
        require(os.getuid() == current["uid"] > 0 and os.getgid() == current["gid"] > 0, "nonroot MainPID")
        env = {k:v for k,v in os.environ.items() if not k.upper().startswith(("DOTNET_","COMPLUS_","CORECLR_","NUGET_","MSBUILD","EXECUTION_LAB_","KESTREL__"))}
        env.update(DOTNET_CLI_HOME=str(private/"cli"),NUGET_PACKAGES=str(private/"nuget"),NUGET_HTTP_CACHE_PATH=str(private/"http"),TEMP=str(private),TMP=str(private),TMPDIR=str(private))
        os.environ.clear();os.environ.update(env)
        import importlib.util
        spec = importlib.util.spec_from_file_location("execution02_products",ROOT/"scripts/qualify_tech_refresh.py")
        products = importlib.util.module_from_spec(spec);spec.loader.exec_module(products)
        from types import SimpleNamespace
        products.ci_products(SimpleNamespace(),{"policyPath":str(args.ci_policy),"policySha256":args.ci_policy_sha256,"current":current},private,
            (normal_module(),ctx,str(Path(os.environ["RUNNER_TEMP"])/("sdk11-normal-02-"+private.name))))
        return 0
    current = ci_observe(args.ci_rid)
    require(current["source"] == policy["consumerSource"], "exact current CI source")
    for key, relative in (("profile","tools/sdk11-own-profile.json"),("sourcePinTable","tools/sdk11-own-source-pins.json"),
                          ("ownContract","docs/SDK11-CONSUMER-CONTRACT.json"),("producerInterface","tools/dotnet11-host-qualification.schema.json"),
                          ("producerFact","tools/sdk11-normal/accepted-linux-fact.json")):
        require(Path(policy[key]["path"]).resolve() == ROOT/relative and sha(ROOT/relative) == policy[key]["sha256"], "fixed own binding path/hash: " + key)
    if os.name == "nt":
        require(args.ci_control_only, "DENIED_NO_ACCEPTED_PRODUCER_FACT")
        private = Path(os.environ["RUNNER_TEMP"])/("execution02-"+uuid.uuid4().hex);private.mkdir(mode=0o700)
        return ci_controlled(policy,current,private,args,start_ns/1e9)
    require(sys.version_info[:2] == (3,12) and not args.ci_control_only, "normal Linux Python3.12 route only")
    return ci_linux_main(policy,current,args,start_ns,end_ns)

def ci_linux_main(policy,current,args,start_ns,end_ns):
    # Fixed OS starter; the held main worker alone imports/calls shared transport.
    for executable in ("/usr/bin/sudo","/usr/bin/systemd-run","/usr/bin/systemctl"):
        require(sha(executable) == policy["linuxStarterHashes"][executable], "existing trusted starter identity")
    private = Path(os.environ["RUNNER_TEMP"]).resolve()/("execution02-"+uuid.uuid4().hex);private.mkdir(mode=0o700)
    save(private/"context.json",current)
    unit = "execution02-ci-"+uuid.uuid4().hex+".service"
    remaining = min(590,int((start_ns+600*10**9-time.monotonic_ns())/1e9)-5)
    require(remaining > 5, "remaining original row budget")
    command = ["/usr/bin/sudo","-n","/usr/bin/systemd-run","--unit="+unit,"--wait","--pipe","--service-type=exec","--expand-environment=no",
        "--uid="+str(current["uid"]),"--gid="+str(current["gid"]),"--property=MemoryMax=4294967296","--property=MemorySwapMax=0","--property=TasksMax=64",
        "--property=CPUQuota=200%","--property=CPUQuotaPeriodSec=100ms","--property=RuntimeMaxSec="+str(remaining),"--property=TimeoutStopSec=5",
        "--property=KillMode=control-group","--property=SendSIGKILL=yes","--property=FinalKillSignal=SIGKILL"]
    names = ("GITHUB_ACTIONS","GITHUB_WORKSPACE","RUNNER_ENVIRONMENT","RUNNER_OS","RUNNER_NAME","RUNNER_TEMP","ImageOS","ImageVersion","GITHUB_REPOSITORY","GITHUB_RUN_ID","GITHUB_RUN_ATTEMPT","GITHUB_JOB","GITHUB_SHA","RUNNER_TRACKING_ID")
    command += ["--setenv="+name+"="+os.environ[name] for name in names]
    command += ["--setenv=PATH=/usr/bin:/bin",sys.executable,"-I","-B",str(Path(__file__).resolve()),"--ci","--ci-worker","--ci-unit",unit,
        "--ci-policy",str(args.ci_policy),"--ci-policy-sha256",args.ci_policy_sha256,"--ci-rid","linux-x64","--ci-row-start",str(start_ns),
        "--ci-context",str(private/"context.json"),"--ci-context-sha256",sha(private/"context.json")]
    def properties():
        raw = subprocess.check_output(["/usr/bin/systemctl","show",unit,"--property=MainPID,ControlPID,Result,ExecMainStatus,ControlGroup"],text=True,timeout=3)
        return dict(x.split("=",1) for x in raw.splitlines() if "=" in x)
    held_fd = None;process = None;failure = None;terminal = False
    try:
        with (private/"worker.log").open("xb") as log:
            process = subprocess.Popen(command,stdout=log,stderr=subprocess.STDOUT)
            until = min(end_ns-10*10**9,time.monotonic_ns()+10*10**9)
            while time.monotonic_ns() < until:
                props = properties();pid = int(props.get("MainPID","0"))
                if pid and Path("/proc",str(pid),"status").exists():
                    status = dict(x.split(":",1) for x in Path("/proc",str(pid),"status").read_text().splitlines() if ":" in x)
                    if status["State"].strip().startswith("T"):
                        break
                require(process.poll() is None, "service exited before hold")
                time.sleep(.05)
            else:
                raise Hold("own stopped MainPID deadline")
            require(hasattr(os,"pidfd_open") and hasattr(signal,"pidfd_send_signal"), "retained pidfd required")
            held_fd = os.pidfd_open(pid,0)
            identity = proc_identity(pid)
            cg = props["ControlGroup"];require(cg == "/system.slice/"+unit, "own service group")
            cgroot = Path("/sys/fs/cgroup"+cg)
            limits = {k:(cgroot/k).read_text().strip() for k in ("memory.max","memory.swap.max","pids.max","cpu.max")}
            members = [int(x) for x in (cgroot/"cgroup.procs").read_text().split()]
            held = {"pid":pid,"mainPID":pid,"processStartIdentity":identity,"uid":int(status["Uid"].split()[1]),"gid":int(status["Gid"].split()[1]),
                "cgroup":cg,"kernelLimits":limits,"state":"T","membershipBeforeRelease":pid in members,"retainedStartHandle":True,
                "supervisorPID":os.getpid(),"supervisorStartIdentity":proc_identity(os.getpid())}
            hashes = {"contract":sha(ROOT/"docs/SDK11-CONSUMER-CONTRACT.json"),"profile":sha(ROOT/"tools/sdk11-own-profile.json"),"controller":sha(__file__)}
            bootstrap = {"pythonVersion":sys.version.split()[0],"pythonExeSha256":sha(Path(sys.executable).resolve()),"gitSha256":sha("/usr/bin/git"),"systemctlSha256":sha("/usr/bin/systemctl")}
            caps,admission,ctx = normal_documents(policy,current,held,private,start_ns,end_ns,bootstrap,hashes,load(ROOT/"tools/sdk11-own-source-pins.json"))
            save(private/"own-caps.json",caps);save(private/"consumer-admission.json",admission);save(private/"normal-context.json",ctx)
            save(private/"containment.json",{"caps":CAPS,"readback":limits,"child":{"pid":pid,"suspendedMember":True},"launcherSha256":sha(__file__),"currentJob":current["job"],"rid":"linux-x64"})
            require(proc_identity(pid) == identity and properties()["MainPID"] == str(pid), "retained worker identity before release")
            signal.pidfd_send_signal(held_fd,signal.SIGCONT)
            while process.poll() is None:
                require(time.monotonic_ns() < start_ns+600*10**9, "original row work deadline")
                size1,logs1 = footprint(ROOT,ROOT);size2,logs2 = footprint(private,private)
                sdk_scope = Path(os.environ["RUNNER_TEMP"])/("sdk11-normal-02-"+private.name)
                sdk_size,sdk_logs = footprint(sdk_scope,sdk_scope) if sdk_scope.exists() else (0,0)
                size2 += sdk_size;logs2 += sdk_logs
                require(size1+size2 <= CAPS["workspaceBytes"] and logs1+logs2 <= CAPS["logBytes"], "row output bounds")
                time.sleep(.2)
            require(process.returncode == 0, "main worker failed")
    except BaseException as exc:
        failure = str(exc)
    finally:
        # No foreign reset/root repair. On failure the already-owned kernel timer
        # must finish within the original deadline; unavailable metadata is HOLD.
        if process is not None and process.poll() is None:
            try:process.wait(timeout=max(.001,(end_ns-time.monotonic_ns())/1e9-5))
            except subprocess.TimeoutExpired:failure = (failure or "")+"; owned timer terminal unknown"
        try:
            props = properties();group = props["ControlGroup"]
            require(group == "/system.slice/"+unit, "terminal group metadata missing")
            populated = dict(x.split() for x in (Path("/sys/fs/cgroup"+group)/"cgroup.events").read_text().splitlines())["populated"]
            import select
            held_terminal = held_fd is not None and bool(select.select([held_fd],[],[],0)[0])
            terminal = held_terminal and props["MainPID"] == props["ControlPID"] == "0" and populated == "0" and props["ExecMainStatus"] == "0" and props["Result"] == "success"
            save(private/"root-terminal.json",{"unit":unit,"properties":props,"populated":populated,"heldPidfdTerminal":held_terminal,"terminal":terminal})
        except BaseException as exc:failure = (failure or "")+"; terminal metadata: "+str(exc)
        if held_fd is not None:os.close(held_fd)
        save(private/"consumer-terminal.json",{"terminal":terminal,"failure":failure,"current":current,"caps":CAPS})
    require(terminal and failure is None and time.monotonic_ns() < end_ns,"row HOLD unless own actual terminal proof")
    return 0


def ci_controlled(policy, current, private, args, row_start):
    # Own native controls before every worker/acquisition/materialization/SDK/product command.
    require(policy["caps"] == CAPS, "own02 caps, not producer caps")
    controller = windows_class()(policy) if os.name == "nt" else Linux(policy)
    code = None
    terminal = False
    failure = None
    try:
        env = {k:v for k,v in os.environ.items() if not k.upper().startswith(("DOTNET_","COMPLUS_","CORECLR_","NUGET_","MSBUILD","EXECUTION_LAB_","KESTREL__"))}
        env.update(DOTNET_CLI_HOME=str(private/"cli"),NUGET_PACKAGES=str(private/"nuget"),NUGET_HTTP_CACHE_PATH=str(private/"http"),TEMP=str(private),TMP=str(private),TMPDIR=str(private))
        save(private/"ci-binding.json",{"policyPath":str(args.ci_policy),"policySha256":args.ci_policy_sha256,"current":current,"caps":CAPS})
        command = [sys.executable,"-I","-B",str(ROOT/"scripts/qualify_tech_refresh.py"),"--phase","ci-all",
                   "--binding",str(private/"ci-binding.json"),"--binding-sha256",sha(private/"ci-binding.json"),"--work",str(private)]
        with (private/"worker.log").open("xb") as log:
            if args.ci_control_only:
                command = [sys.executable,"-I","-B","-c","import os,json;print(json.dumps({'sdkCommands':0,'pid':os.getpid()}))"]
            controller.start(command,env,log)
            save(private/"containment.json",{"caps":CAPS,"readback":controller.readback,"child":controller.child,
                 "launcherSha256":sha(__file__),"currentJob":current["job"],"rid":current["rid"]})
            controller.resume()
            while (code := controller.poll()) is None:
                require(time.monotonic()-row_start < 600, "remaining row work deadline")
                size1, logs1 = footprint(ROOT, ROOT)
                size2, logs2 = footprint(private, private)
                require(size1+size2 <= CAPS["workspaceBytes"] and logs1+logs2 <= CAPS["logBytes"], "row output bounds")
                time.sleep(.2)
            require(code == 0, "consumer worker failed")
    except BaseException as error:
        failure = str(error)
    finally:
        try:
            terminal = controller.finish()
        except BaseException as cleanup:
            failure = (failure or "") + "; terminal: " + str(cleanup)
        save(private/"consumer-terminal.json",{"exit":code,"terminal":terminal,"failure":failure,"current":current,
             "caps":CAPS,"readback":controller.readback,"childTerminalProof":getattr(controller,"child_proof",None)})
    require(terminal and failure is None and time.monotonic()-row_start < 620, "row incomplete")
    return 0

def ci_entry():
    require(sys.version_info[:2] >= (3,12), "preinstalled Python >=3.12 required; no install")
    p = argparse.ArgumentParser()
    p.add_argument("--ci", action="store_true")
    p.add_argument("--ci-worker", action="store_true")
    p.add_argument("--ci-control-only", action="store_true")
    p.add_argument("--ci-row-start", default="")
    p.add_argument("--ci-context", type=Path)
    p.add_argument("--ci-context-sha256")
    p.add_argument("--ci-unit", default="")
    p.add_argument("--ci-policy", type=Path, required=True)
    p.add_argument("--ci-policy-sha256", required=True)
    p.add_argument("--ci-rid", choices=("win-x64","linux-x64"), required=True)
    return ci_row(p.parse_args())

if __name__ == "__main__":
    try:
        sys.exit(ci_entry() if "--ci" in sys.argv else main())
    except Hold as error:
        print(json.dumps({"status": "COMPLETED_INPUT_DENIAL", "reason": str(error)}))
        sys.exit(2)
