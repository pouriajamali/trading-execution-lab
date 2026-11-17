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
LINROOT = "/home/ubuntu/execution02-local-net11-20261117/repo"
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

def footprint(log_root=None, workspace=ROOT, npm_links=None):
    total = logs = 0
    for base, dirs, files in os.walk(workspace, followlinks=False):
        for name in [*dirs, *files]:
            p = Path(base) / name
            if p.is_symlink():
                target = (npm_links or {}).get(p)
                require(target is not None and p.resolve(strict=True) == target.resolve(strict=True)
                        and target.is_file() and not target.is_symlink(), "workspace link outside exact locked npm bin")
            else:
                require(not p.is_junction(), "workspace junction")
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

def locked_npm_bin_links():
    # npm creates these four file links on Linux. Their exact destinations come
    # from the signed frontend lock; no directory, junction or escape is allowed.
    node_root = ROOT/"OperatorPanel/node_modules"
    lock = load(ROOT/"OperatorPanel/package-lock.json")
    links = {}
    for package, row in lock["packages"].items():
        for name, relative in row.get("bin", {}).items():
            require(package.startswith("node_modules/") and "/" not in name and "\\" not in name,
                    "locked npm bin name")
            target = ROOT/"OperatorPanel"/package/relative
            require(target.absolute().is_relative_to(node_root) and ".." not in Path(relative).parts,
                    "locked npm bin destination")
            require(node_root/".bin"/name not in links, "ambiguous locked npm bin")
            links[node_root/".bin"/name] = target
    require(len(links) <= 32, "locked npm bin count")
    return links

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
    if b["mode"] == "LOCAL_NATIVE_02_20261117":
        require(b["sourceCommit"] == subprocess.check_output(["git","rev-parse","HEAD"],cwd=ROOT,text=True,timeout=5).strip()
                and b["sourceTree"] == subprocess.check_output(["git","rev-parse","HEAD^{tree}"],cwd=ROOT,text=True,timeout=5).strip()
                and not subprocess.check_output(["git","status","--porcelain"],cwd=ROOT,timeout=5), "exact clean local source")
        require(names == set(subprocess.check_output(["git","ls-files","--cached","-z"],cwd=ROOT,timeout=5).decode().rstrip("\0").split("\0")), "complete current local source inventory")
        require(b["localProfileSha256"] == sha(ROOT/"tools/sdk11-own-local-profile.json"), "own local profile")
        profile = load(ROOT/"tools/sdk11-own-local-profile.json")
        require(profile["projectId"] == "02" and profile["caps"] == CAPS
                and profile["phaseDeadlines"] == PHASES and profile["perOSSeconds"] == 2100,
                "original local limits")
        if os.name == "nt":
            import winreg
            with winreg.OpenKey(winreg.HKEY_LOCAL_MACHINE,r"SOFTWARE\Microsoft\Windows NT\CurrentVersion") as key:
                version, build = [winreg.QueryValueEx(key,name)[0] for name in ("DisplayVersion","CurrentBuildNumber")]
            require(version == profile["windows"]["displayVersion"] == "26H2" and build == profile["windows"]["build"] == "26300"
                    and profile["windows"]["explicitHumanExperimentalConsent"] is True, "exact experimental Windows consent")
        else:
            release = dict(line.split("=",1) for line in Path("/etc/os-release").read_text().splitlines() if "=" in line)
            require(release.get("ID") == "ubuntu" and release.get("VERSION_ID","").strip('"') == "24.04"
                    and os.getuid() == b["uid"] == 1000 and os.getgid() == b["gid"] == 1000
                    and Path("/proc/1/comm").read_text().strip() == "systemd", "own actual Ubuntu local host")
        require(sha(ROOT/"tools/sdk11-normal-inputs.lock.json") == NORMAL_PINS["tools/sdk11-normal-inputs.lock.json"], "common catalog unchanged")
    else:
        require(os.name == "nt", "legacy local Linux R3 STOP")
        require(args.phase == "probe" and b["mode"] == "CONTROL_PROBE_ONLY", "legacy scope remains control-only")
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
            self.job_name = b.get("ciJobName")
            if self.job_name is not None:
                import re
                require(b.get("state") == "EXACT_CI_CONSUMER_ADMISSION" and
                        re.fullmatch(r"Local\\execution02-ci-[a-f0-9]{32}", self.job_name), "own named CI Job")
            c.set_last_error(0)
            self.job = k.CreateJobObjectW(None, self.job_name)
            already_exists = c.get_last_error() == 183
            require(self.job, "create own Job failed")
            if self.job_name and already_exists:
                k.CloseHandle(self.job)
                raise Hold("owned random Job already exists")
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
            self.limits.basic.flags = 0x2308 if self.job_name else 0x2318
            self.limits.basic.affinity = 0 if self.job_name else sum(bits)
            self.limits.basic.processes = 64
            self.limits.processMemory = self.limits.jobMemory = CAPS["memoryBytes"]
            require(k.SetInformationJobObject(self.job, 9, c.byref(self.limits), c.sizeof(self.limits)), "Job cap assignment failed")
            actual = Extended()
            require(k.QueryInformationJobObject(self.job, 9, c.byref(actual), c.sizeof(actual), None), "Job cap query")
            require(actual.basic.flags == self.limits.basic.flags and (self.job_name is not None or actual.basic.affinity == self.limits.basic.affinity)
                    and actual.basic.processes == 64 and actual.processMemory == actual.jobMemory == CAPS["memoryBytes"], "Job readback mismatch")
            self.readback = {"flags": actual.basic.flags, "affinity": actual.basic.affinity, "cpuCount": len(bits),
                             "activeProcessLimit": 64, "processMemory": actual.processMemory, "jobMemory": actual.jobMemory}
            if self.job_name:
                class CPU(c.Structure):
                    _fields_ = [("flags", w.DWORD), ("rate", w.DWORD)]
                k.GetActiveProcessorCount.argtypes = [w.WORD]
                k.GetActiveProcessorCount.restype = w.DWORD
                logical = int(k.GetActiveProcessorCount(0xffff))
                require(logical > 0, "own logical CPU readback")
                requested = CPU(5, max(1, min(10000, int(10000 * CAPS["cpuCores"] / logical))))
                require(k.SetInformationJobObject(self.job, 15, c.byref(requested), c.sizeof(requested)), "own CPU Job cap")
                cpu = CPU()
                require(k.QueryInformationJobObject(self.job, 15, c.byref(cpu), c.sizeof(cpu), None)
                        and cpu.flags == 5 and cpu.rate == requested.rate, "own CPU Job readback")
                self.readback.update(jobName=self.job_name, cpuRate=int(cpu.rate), logicalHostCpu=logical,
                                     effectiveCpuCores=cpu.rate * logical / 10000)

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
    phase_limit = PHASES[args.phase]
    if b.get("preparePrivateLinuxTools") is True:
        exception = load(ROOT/"tools/local-linux-tools.lock.json")["transferException"]
        require(b["mode"] == "LOCAL_NATIVE_02_20261117" and os.name == "nt" and args.phase == "frontend"
                and exception["explicitHumanConsent"] is True and exception["totalSeconds"] == 480,
                "exact human private-tool data exception only")
        phase_limit = 480
        transfers = [p for p in previous if p.get("purpose") == "LOCAL_PRIVATE_TOOL_DATA"]
        require(transfers and all(p["terminal"] is True for p in transfers), "retained all own transfer attempts")
        b["priorAttemptSeconds"] = sum(p["elapsedSeconds"] for p in transfers)
    prior_attempt = b.get("priorAttemptSeconds",0)
    require(type(prior_attempt) in (int,float) and 0 <= prior_attempt < phase_limit, "prior phase budget")
    if prior_attempt and not b.get("preparePrivateLinuxTools"):
        retained = b.get("retainedPhaseReceipt",b.get("retainedQualificationMetadata",{}))
        prior = load(Path(retained["directory"])/"receipt.json",retained["receiptSha256"])
        require(prior["terminal"] is True and prior["elapsedSeconds"] == prior_attempt, "actual retained phase budget")
    phase_budget = min(phase_limit-prior_attempt,2100-spent)
    require(phase_budget > 5, "remaining original local phase budget")
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
        footprint(ROOT, ROOT, locked_npm_bin_links())
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
        if args.phase == "probe" and b["mode"] == "CONTROL_PROBE_ONLY":
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
                _, logs = footprint(ROOT, ROOT, locked_npm_bin_links())
                require(logs <= CAPS["logBytes"], "aggregate log cap exceeded")
                require(time.monotonic() - start <= phase_budget - 5, "phase deadline")
                if os.name != "nt":
                    require(controller.inspect() == controller.readback, "kernel caps changed")
                    controller.capture_owned()
                time.sleep(.2)
            require(code == 0, "completed child failure")
            _, logs = footprint(ROOT, ROOT, locked_npm_bin_links())
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
        if time.monotonic() - start > phase_budget:
            failure = "phase/OS deadline exceeded including teardown"
        receipt = {"status": "COMPLETED" if failure is None and terminal else "FAILED_OR_INCOMPLETE",
                   "purpose": "LOCAL_PRIVATE_TOOL_DATA" if b.get("preparePrivateLinuxTools") is True else "LOCAL_NATIVE_QUALIFICATION" if b["mode"] == "LOCAL_NATIVE_02_20261117" and args.phase == "probe" else "CONTROL_PROBE" if args.phase == "probe" else "LOCAL_PHASE", "phase": args.phase,
                   "phaseBudgetSeconds":phase_budget,"priorAttemptSeconds":prior_attempt,
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
            "runnerName":rows[0]["runner_name"],"startedAt":rows[0]["started_at"]},"metadataSha256":hashlib.sha256(raw).hexdigest()}

NORMAL_PINS = {'docs/SDK11_SHARED_INPUT_INTERFACE.json': 'eca0dd5cfe425623119aff5b05dcf70c881ce2c23414be48fb7a74920c2f89d9', 'tools/check_dotnet11.py': 'c37e2f48ee21ef1f02e4afb2bb1cd0af397781e487265c31e43fe06ea182befd', 'tools/dotnet11-host-qualification.schema.json': '63e04fa5d270c87b93e6e1f4c38bfbcf336b950b39fe1854dc4e514f0661f14c', 'tools/materialize_qualification_linux.py': '5f0dbb951cbe615d8c6dd9edbb63b11143cc457319bdcc9000ea9a486f660fb8', 'tools/normal_windows_input.py': '5bab5ee0f8fdd724706fad0735a81aa1d89e747cf651e9bb0a4760052fed6312', 'tools/qualification_input_guard.py': '7420b08d78d3b1476be41385d179a42212a2a7e1a965a8d8ea3b67bb14da7925', 'tools/sdk11-native-inputs.lock.json': '1f24dedfc1ff63c19948a3a9786431a3a3b888defbcff70fd3c4e8c827b3cdf4', 'tools/sdk11-normal-inputs.lock.json': '8995a4d296afbfcdf8e267e1923a4de5365b7fa1ef58457add433dfb6df33e23', 'tools/sdk11-normal-windows-admission.json': '21d186215b96b05944280ff986b93e3931cd5ed38322e009a4b9a58ac361f2b5', 'tools/sdk11-normal/.gitattributes': '2a207309ad9dd473a1bf02f2bacda4adea72588a203d303f3cea59d00b4a0173', 'tools/sdk11-normal/accepted-linux-acceptance.json': '0452e1f3b4f2662d57e9b273428bb37ab0c5a733551a92394ca2a4e8b9b4ac08', 'tools/sdk11-normal/accepted-linux-fact.json': '757abf2d3dde65d10cd895cfc97eaeccb7fc11e8685b94ad046e6a8ec8829007', 'tools/sdk11-normal/accepted-windows-acceptance.json': '9713a70f809ac7f50a1c73650fc6d3390bccda109e7a2d15c9be581ff91dc8f6', 'tools/sdk11-normal/accepted-windows-fact.json': 'ec8e9b405ca74bd7bbc748575265de2555056d84ff5780a8979bbb01cbd27c48', 'tools/sdk11-normal/native-linux/FINAL-CANDIDATE.json': '411260d44b31935145d141a53b60b57e7d0acc5f566f3111685c10b310e61100', 'tools/sdk11-normal/native-linux/cleanup-terminal.json': '607e2d703cbaa4655666c72c169fac071b2f7eb794b0338b05721ba02f1d0d61', 'tools/sdk11-normal/native-linux/curation-current-network-deny.json': 'f1fd41f5abac2f7dcf6bba89f7ee40421df933f270ffb9573c83eb1d459e32a0', 'tools/sdk11-normal/native-linux/curation-worker.json': '3f8f4fcc52e4943602cdd66e97814404e6ac46226d76b59f0b3b614916364dc7', 'tools/sdk11-normal/native-linux/members-0.ndjson': '627a75db249945a08c77a107746b628e8186a1fc8f4949c02e72ec5140f7776a', 'tools/sdk11-normal/native-linux/members-1.ndjson': '85783bebf9d0ea565708c3e976fdd2b5a220beca615a553160e00cb522910875', 'tools/sdk11-normal/native-linux/members-2.ndjson': 'ff90b05a7fba22c7f65332691367a8e14f6a83e772c8e4fca9e29208f8074695', 'tools/sdk11-normal/native-linux/metadata/pki-0.der': '3e9099b5015e8f486c00bcea9d111ee721faba355a89bcf1df69561e3dc6325c', 'tools/sdk11-normal/native-linux/metadata/pki-1.der': '46011ede1c147eb2bc731a539b7c047b7ee93e48b9d3c3ba710ce132bbdfac6b', 'tools/sdk11-normal/native-linux/metadata/pki-2.der': 'ca0b1554ecd901ea19dcad8749e9f2648c8d6dfcea1add9d2c2109415bb82ccd', 'tools/sdk11-normal/native-linux/metadata/pki-3.der': '552f7bdcf1a7af9e6ce672017f4f12abf77240c78e761ac203d1d9d20ac89988', 'tools/sdk11-normal/native-linux/metadata/pki-4.der': 'ec80f6afd1fd52e7b59eedbaf07a24c33c622e208e4a7c3c21636962d30c62e9', 'tools/sdk11-normal/native-linux/metadata/pki-5.der': 'f46d22f778b465fcfaeface615e2e8a359af42a000246d6a420671ef654bf800', 'tools/sdk11-normal/native-linux/metadata/pki-6.der': '41e687c3f7c0316762c0933d2475e7b5256e478042e87592d1fcfe926342f244', 'tools/sdk11-normal/native-linux/metadata/pki-7.der': '057cf252d73ef58e8188da588da4eccc7e7aa2b7708b9455da6e7b42c8c1c594', 'tools/sdk11-normal/native-linux/metadata/pki-8.der': 'f46d22f778b465fcfaeface615e2e8a359af42a000246d6a420671ef654bf800', 'tools/sdk11-normal/native-linux/metadata/repository.json': '5f45cbf2d7f8a4b57fea6e43bb603d29a0682058a71eb61d900db74860d210b0', 'tools/sdk11-normal/native-linux/metadata/repository.json.wire': 'c572b43f8bf2e880ae6d20b4dcc6cbd9bf0579de129d7a72ca97bcdbf6619c00', 'tools/sdk11-normal/native-linux/metadata/service.json': '5e763505b0587d013ddda3ddb24e80d3c6590ac6ce60916d4278fb9df018e07f', 'tools/sdk11-normal/native-linux/metadata/service.json.wire': 'd9c396850421800c9cbd379aab5ce69cdaff9a36aeab75b1ad5dbe63036071af', 'tools/sdk11-normal/native-linux/metadata/servicing.json': '5c40c300da0264784179b299169e8c15cb02f8a1e0363dede2a4f5046de1fcc0', 'tools/sdk11-normal/native-linux/metadata/servicing.json.wire': '894599ee4bcbe2766da9403a35f6b8af10931f8a190eac2a9c9b40709b20cccd', 'tools/sdk11-normal/native-linux/metadata/vulnerability-index.json': '32aedfc995e5b6d37916e22401dbf70a11c5f320c9488c26753fcf4ae9d92558', 'tools/sdk11-normal/native-linux/metadata/vulnerability-index.json.wire': '7b840b6e9ce6f7d328e9a57115a5aaf54478ac6dace0d084fb6e8d5b35b55321', 'tools/sdk11-normal/native-linux/metadata/vulnerability-page-0.json': '290f263aff7519b36e1beb86c315334f3dadb4783152b91c360d17164c4a628b', 'tools/sdk11-normal/native-linux/metadata/vulnerability-page-0.json.wire': '84e9938010713e92d67961adce10c5f8a24cb9b9d0807df849e98094198ffdac', 'tools/sdk11-normal/native-linux/metadata/vulnerability-page-1.json': '44136fa355b3678a1146ad16f7e8649e94fb4fc21fe77e8310c060f61caaff8a', 'tools/sdk11-normal/native-linux/metadata/vulnerability-page-1.json.wire': 'ca1436826f77887edb26d32b6a5853d0c83578cab2d0892484d8d99f95e138f1', 'tools/sdk11-normal/native-linux/nuget-0.log': '605f072b2d71662da44f68178f11cd3024770a68a6f22aa36f87883065ff508e', 'tools/sdk11-normal/native-linux/nuget-1.log': '9072b7dce3db3a6210c80829172c3da5cea70d92dfb0d56da591ebfb36b1cc7e', 'tools/sdk11-normal/native-linux/nuget-2.log': '3d5343aa2b80d0eed1f2e337c6b4efcaebd05a1e677521af3026eca4ca6e21b7', 'tools/sdk11-normal/native-linux/original-0-1.data': 'c510e4f45c01dd85947b02ddcc60b2c4a8a6e7030959c918399008d7436fc3a8', 'tools/sdk11-normal/native-linux/original-0-143.data': 'f9d28824993ffe5f74052772ca7af0b827774c4a7810ee3bb984fc7ca9256155', 'tools/sdk11-normal/native-linux/original-0-2.data': 'fe970484b338399def0b81b24d8a6005122d5c9f559a257c2ad22cbb83644cab', 'tools/sdk11-normal/native-linux/original-0-4.data': 'cfc21f5e8bd655ae997eec916138b707b1d290b83272c02a95c9f821b8c87310', 'tools/sdk11-normal/native-linux/original-1-1.data': 'd6cf0867b865f014b38f79408c7303c580eaa03736e114071f90c4ce6f96cadb', 'tools/sdk11-normal/native-linux/original-1-18.data': 'e6b246d5bf927b4dcfc7655aa0605c8ed10885cbd708cc96ad21f0d55e21e6b7', 'tools/sdk11-normal/native-linux/original-1-4.data': 'cfc21f5e8bd655ae997eec916138b707b1d290b83272c02a95c9f821b8c87310', 'tools/sdk11-normal/native-linux/original-1-6.data': '4790bb15f0edd1b105aecb05174fc6c589d4d9fad0c50616ef5f7dc365f1c8a6', 'tools/sdk11-normal/native-linux/original-2-1.data': 'b018757b94b545a3e12a6e655541eec0af12fd425cf077191c5b13d023df8244', 'tools/sdk11-normal/native-linux/original-2-210.data': 'e5d89bd848a1a32e8f18aa47dd04273d81fb045472ca5d6c6be4ddadf2003fbe', 'tools/sdk11-normal/native-linux/original-2-4.data': 'cfc21f5e8bd655ae997eec916138b707b1d290b83272c02a95c9f821b8c87310', 'tools/sdk11-normal/native-linux/original-2-6.data': '4790bb15f0edd1b105aecb05174fc6c589d4d9fad0c50616ef5f7dc365f1c8a6', 'tools/sdk11-normal/native-linux/public-original-input-receipt.json': '9e0cd4c50e51d640cbebf9ec94903f2cd56a92531b6378eb8fc2aae9da08b6d3', 'tools/sdk11-normal/native-linux/recovered-metadata-0.json': '31971d09fd6c58f9ebb0c70d2cc04e319405cf01a10671789c28fff18f144227', 'tools/sdk11-normal/native-linux/recovered-metadata-1.json': 'e08766fa5d8bd82ce74b2f31b9a1a128c3650f5a97fe304d0f2e95ed4bd9cc99', 'tools/sdk11_ci_facts.py': '6bb0fe5199377dfdb0caed76cf274bcef631205648d9dbf0d67e1f43433e9a7e', 'tools/test_shared_normal_windows_delta.py': '220b39d935522d4cc1e8dcd08fcce880f1550c61baab6957b734cf55ba55caad'}

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

def windows_documents(policy, current, controller, private, start_ns, end_ns):
    require(policy["state"] == "EXACT_CI_CONSUMER_ADMISSION" and current["rid"] == "win-x64"
            and controller.child["suspendedMember"] is True, "own held Windows route")
    readback = controller.readback
    held = {"pid":controller.child["pid"],"processStartIdentity":"FILETIME:"+str(controller.child["start"]),
        "jobName":readback["jobName"],"memoryMaxBytes":readback["jobMemory"],"tasksMax":readback["activeProcessLimit"],
        "cpuRate":readback["cpuRate"],"logicalHostCpu":readback["logicalHostCpu"]}
    require(held["memoryMaxBytes"] == CAPS["memoryBytes"] and held["tasksMax"] == CAPS["tasks"]
            and 0 < readback["effectiveCpuCores"] <= CAPS["cpuCores"]
            and end_ns-start_ns == 620*10**9, "own Windows caps/original row")
    ctx = {"projectId":"02","repository":current["job"]["repository"],"checkout":str(ROOT),
        "controller":str(Path(__file__).resolve()),"contract":str(ROOT/"docs/SDK11-CONSUMER-CONTRACT.json"),
        "profile":str(ROOT/"tools/sdk11-own-windows-profile.json"),"sourcePins":str(ROOT/"tools/sdk11-own-source-pins.json"),
        "admission":str(private/"consumer-admission.json"),"capsEvidence":str(private/"own-caps.json"),
        "expectedSourceCommit":current["source"]["commit"],"expectedSourceTree":current["source"]["tree"],
        "rowStartedMonotonicNs":start_ns,"deadlineMonotonicNs":end_ns,"supervisorPID":os.getpid(),
        "supervisorStartIdentity":"FILETIME:"+str(controller.owner_start)}
    caps = {"schema":"sdk11-own-current-cap-evidence/v1","projectId":"02","repository":ctx["repository"],
        "sourceCommit":ctx["expectedSourceCommit"],"sourceTree":ctx["expectedSourceTree"],
        "profileSha256":sha(ctx["profile"]),"controllerSha256":sha(__file__),"worker":held,
        "heldBeforeExec":{**held,"state":"SUSPENDED","membershipBeforeRelease":True,"retainedStartHandle":True},
        "supervisor":{"pid":ctx["supervisorPID"],"processStartIdentity":ctx["supervisorStartIdentity"],"deadlineMonotonicNs":end_ns},
        "rowStartedMonotonicNs":start_ns,"deadlineMonotonicNs":end_ns,
        "bootstrap":{"pythonVersion":sys.version.split()[0],"pythonExeSha256":sha(Path(sys.executable).resolve()),
                     "gitSha256":sha("C:/Program Files/Git/cmd/git.exe")}}
    admission = json.loads(json.dumps(policy["consumerAdmission"]))
    require(admission["projectId"] == "02" and admission["producerFactSha256"] == NORMAL_PINS["tools/sdk11-normal/accepted-windows-fact.json"], "own accepted Windows history")
    bound = admission["admittedFor"]
    pins = load(ctx["sourcePins"])
    source_hash = hashlib.sha256(json.dumps(pins["sourcePins"],sort_keys=True,separators=(",",":"),ensure_ascii=False).encode()).hexdigest()
    require(bound["controllerSha256"] == caps["controllerSha256"] and bound["profileSha256"] == caps["profileSha256"]
            and bound["contractSha256"] == sha(ctx["contract"]) and bound["sourcePinTableSha256"] == source_hash,
            "own Windows frozen source/profile")
    admission["currentExecution"] = {"runId":current["job"]["runId"],"job":current["job"]["jobKey"],
        "attempt":current["job"]["attempt"],"instanceId":current["instanceId"],
        "ownCapsEvidenceSha256":hashlib.sha256((json.dumps(caps,indent=2)+"\n").encode()).hexdigest()}
    return caps, admission, ctx

def normal_module():
    import importlib.util
    for name, expected in NORMAL_PINS.items():
        require(sha(ROOT/name) == expected, "shared04 byte identity: " + name)
    spec = importlib.util.spec_from_file_location("execution02_shared_normal",ROOT/"tools/check_dotnet11.py")
    module = importlib.util.module_from_spec(spec)
    sys.modules[spec.name] = module
    spec.loader.exec_module(module)
    return module

def ci_stop_post(policy, args):
    """Same nonroot service: retain typed exit evidence before unit collection."""
    current = load(args.ci_context, args.ci_context_sha256)
    private = args.ci_context.parent
    require(private.parent == Path(os.environ["RUNNER_TEMP"]).resolve()
            and os.getuid() == current["uid"] > 0 and os.getgid() == current["gid"] > 0,
            "own nonroot stop observer")
    group = Path("/proc/self/cgroup").read_text().strip()
    require(group == "0::/system.slice/" + args.ci_unit, "own stop observer group")
    root = Path("/sys/fs/cgroup/system.slice") / args.ci_unit
    limits = {key:(root/key).read_text().strip() for key in ("memory.max","memory.swap.max","pids.max","cpu.max")}
    members = {int(pid) for pid in (root/"cgroup.procs").read_text().split()}
    require(os.getpid() in members, "stop observer membership")
    save(private/"stop-outcome.json", {"unit":args.ci_unit,"currentJob":current["job"],
        "serviceResult":os.environ.get("SERVICE_RESULT","UNKNOWN"),
        "exitCode":os.environ.get("EXIT_CODE","UNKNOWN"),"exitStatus":os.environ.get("EXIT_STATUS","UNKNOWN"),
        "observerPID":os.getpid(),"observerStart":proc_identity(os.getpid()),
        "uid":os.getuid(),"gid":os.getgid(),"kernelLimits":limits,
        "remainingPopulationExcludingObserver":len(members-{os.getpid()})})
    return 0

def ci_terminal_values(unit, current, stop, props, launcher_terminal, launcher_exit, held_terminal, group_exists, populated):
    # A collected unit is not success by absence alone: require the durable
    # original service exit, original launcher and held worker to be terminal.
    expected = {"memory.max":"4294967296","memory.swap.max":"0","pids.max":"64","cpu.max":"200000 100000"}
    if not (launcher_terminal is True and launcher_exit == 0 and held_terminal is True):
        return False
    if not (stop.get("unit") == unit and stop.get("currentJob") == current["job"]
            and stop.get("uid") == current["uid"] > 0 and stop.get("gid") == current["gid"] > 0
            and stop.get("serviceResult") == "success" and stop.get("exitCode") == "exited"
            and stop.get("exitStatus") == "0" and stop.get("remainingPopulationExcludingObserver") == 0
            and stop.get("kernelLimits") == expected and type(stop.get("observerPID")) is int
            and stop["observerPID"] > 0 and str(stop.get("observerStart", "")).startswith("proc-start:")):
        return False
    if group_exists:
        return (populated == "0" and props.get("Description") == unit
                and props.get("MainPID") == props.get("ControlPID") == "0"
                and props.get("Result") == "success" and props.get("ExecMainStatus") == "0")
    return (props.get("LoadState") == "not-found" or
            (props.get("Description") == unit and props.get("MainPID") == props.get("ControlPID") == "0"
             and props.get("ActiveState") in ("inactive","failed") and props.get("Result") == "success"
             and props.get("ExecMainStatus") == "0"))

def ci_row(args, observed_current=None):
    start_ns = int(args.ci_row_start) if args.ci_row_start else time.monotonic_ns()
    end_ns = start_ns + 620*10**9
    require(start_ns <= time.monotonic_ns() < end_ns, "original row clock")
    policy = load(args.ci_policy,args.ci_policy_sha256)
    require(policy["state"] == "EXACT_CI_CONSUMER_ADMISSION" and policy["caps"] == CAPS, "inert policy cannot execute")
    require(sha(sys.executable) == policy["pythonSha256"] and sha(__file__) == policy["controllerSha256"], "exact controller/bootstrap")
    if args.ci_stop_post:
        require(os.name != "nt" and args.ci_rid == "linux-x64", "Linux stop observer only")
        return ci_stop_post(policy, args)
    if args.ci_worker:
        require(args.ci_rid == ("win-x64" if os.name == "nt" else "linux-x64"), "current main worker RID")
        private = args.ci_context.parent
        require(private.parent == Path(os.environ["RUNNER_TEMP"]).resolve(), "private root")
        if os.name != "nt":
            # Linux self-stop; Windows remains suspended in CreateProcess until
            # the same parent writes/holds the exact current evidence and resumes.
            os.kill(os.getpid(),signal.SIGSTOP)
        ctx = load(private/"normal-context.json")
        require(ctx["deadlineMonotonicNs"] == end_ns and ctx["rowStartedMonotonicNs"] == start_ns, "inherited original deadline")
        current = load(args.ci_context,args.ci_context_sha256)
        if os.name != "nt":
            require(os.getuid() == current["uid"] > 0 and os.getgid() == current["gid"] > 0, "nonroot MainPID")
        env = {k:v for k,v in os.environ.items() if not k.upper().startswith(("DOTNET_","COMPLUS_","CORECLR_","NUGET_","MSBUILD","EXECUTION_LAB_","KESTREL__"))}
        env.update(DOTNET_CLI_HOME=str(private/"cli"),NUGET_PACKAGES=str(private/"nuget"),NUGET_HTTP_CACHE_PATH=str(private/"http"),TEMP=str(private),TMP=str(private),TMPDIR=str(private))
        if os.name == "nt":
            for key in list(env):
                if key.upper() in ("PROGRAMFILES", "PROGRAMFILES(X86)", "PROGRAMW6432"):
                    del env[key]
            for key, directory in (("PROGRAMFILES","programfiles"),("PROGRAMFILES(X86)","programfiles-x86"),("PROGRAMW6432","programfiles")):
                target = private/directory
                target.mkdir(exist_ok=True)
                require(not any(target.iterdir()), "private empty Windows discovery root")
                env[key] = str(target)
        os.environ.clear();os.environ.update(env)
        import importlib.util
        spec = importlib.util.spec_from_file_location("execution02_products",ROOT/"scripts/qualify_tech_refresh.py")
        products = importlib.util.module_from_spec(spec);spec.loader.exec_module(products)
        from types import SimpleNamespace
        products.ci_products(SimpleNamespace(),{"policyPath":str(args.ci_policy),"policySha256":args.ci_policy_sha256,"current":current},private,
            (normal_module(),ctx,str(Path(os.environ["RUNNER_TEMP"])/("sdk11-normal-02-"+private.name))))
        return 0
    current = observed_current if observed_current is not None else ci_observe(args.ci_rid)
    require(current["source"] == policy["consumerSource"], "exact current CI source")
    profile_path = "tools/sdk11-own-windows-profile.json" if args.ci_rid == "win-x64" else "tools/sdk11-own-profile.json"
    fact_path = "tools/sdk11-normal/accepted-windows-fact.json" if args.ci_rid == "win-x64" else "tools/sdk11-normal/accepted-linux-fact.json"
    for key, relative in (("profile",profile_path),("sourcePinTable","tools/sdk11-own-source-pins.json"),
                          ("ownContract","docs/SDK11-CONSUMER-CONTRACT.json"),("producerInterface","tools/dotnet11-host-qualification.schema.json"),
                          ("producerFact",fact_path)):
        require(Path(policy[key]["path"]).resolve() == ROOT/relative and sha(ROOT/relative) == policy[key]["sha256"], "fixed own binding path/hash: " + key)
    from datetime import datetime
    started_wall = datetime.fromisoformat(current["job"]["startedAt"].replace("Z","+00:00")).timestamp()
    require(0 <= time.time()-started_wall <= 60, "actual checkout/metadata bootstrap60 deadline")
    if os.name == "nt":
        private = Path(os.environ["RUNNER_TEMP"])/("execution02-"+uuid.uuid4().hex);private.mkdir(mode=0o700)
        return ci_controlled(policy,current,private,args,start_ns)
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
    import shlex
    observer_argv = [sys.executable,"-I","-B",str(Path(__file__).resolve()),"--ci","--ci-stop-post","--ci-unit",unit,
        "--ci-policy",str(args.ci_policy),"--ci-policy-sha256",args.ci_policy_sha256,"--ci-rid","linux-x64","--ci-row-start",str(start_ns),
        "--ci-context",str(private/"context.json"),"--ci-context-sha256",sha(private/"context.json")]
    for path in (str(ROOT),str(private),sys.executable,str(args.ci_policy)):
        require(not any(char in path for char in ("\n","\r","%","$","\"","'")), "fixed system unit argv path")
    observer = " ".join(shlex.quote(value) for value in observer_argv)
    command = ["/usr/bin/sudo","-n","/usr/bin/systemd-run","--property=Description="+unit,
        "--property=ExecStopPost="+observer,"--unit="+unit,"--wait","--pipe","--service-type=exec","--expand-environment=no",
        "--uid="+str(current["uid"]),"--gid="+str(current["gid"]),"--property=MemoryMax=4294967296","--property=MemorySwapMax=0","--property=TasksMax=64",
        "--property=CPUQuota=200%","--property=CPUQuotaPeriodSec=100ms","--property=RuntimeMaxSec="+str(remaining),"--property=TimeoutStopSec=5",
        "--property=KillMode=control-group","--property=SendSIGKILL=yes","--property=FinalKillSignal=SIGKILL"]
    names = ("GITHUB_ACTIONS","GITHUB_WORKSPACE","RUNNER_ENVIRONMENT","RUNNER_OS","RUNNER_NAME","RUNNER_TEMP","ImageOS","ImageVersion","GITHUB_REPOSITORY","GITHUB_RUN_ID","GITHUB_RUN_ATTEMPT","GITHUB_JOB","GITHUB_SHA","RUNNER_TRACKING_ID")
    command += ["--setenv="+name+"="+os.environ[name] for name in names]
    command += ["--setenv=PATH=/usr/bin:/bin",sys.executable,"-I","-B",str(Path(__file__).resolve()),"--ci","--ci-worker","--ci-unit",unit,
        "--ci-policy",str(args.ci_policy),"--ci-policy-sha256",args.ci_policy_sha256,"--ci-rid","linux-x64","--ci-row-start",str(start_ns),
        "--ci-context",str(private/"context.json"),"--ci-context-sha256",sha(private/"context.json")]
    def properties():
        result = subprocess.run(["/usr/bin/systemctl","show",unit,
            "--property=Id,Description,LoadState,ActiveState,MainPID,ControlPID,Result,ExecMainStatus,ControlGroup"],
            capture_output=True,text=True,timeout=3)
        require(len(result.stdout)+len(result.stderr) <= 16384, "own unit metadata cap")
        values = dict(x.split("=",1) for x in result.stdout.splitlines() if "=" in x)
        require(result.returncode == 0 or values.get("LoadState") == "not-found", "own unit metadata unavailable")
        return values
    require(properties().get("LoadState") == "not-found", "owned random unit must be absent before creation")
    npm_links = locked_npm_bin_links()
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
            cg = props["ControlGroup"];require(cg == "/system.slice/"+unit and props.get("Description") == unit, "own generation-bound service group")
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
                size1,logs1 = footprint(ROOT,ROOT,npm_links);size2,logs2 = footprint(private,private)
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
            props = properties()
            group_path = Path("/sys/fs/cgroup/system.slice")/unit
            group_exists = group_path.is_dir()
            populated = dict(x.split() for x in (group_path/"cgroup.events").read_text().splitlines())["populated"] if group_exists else None
            import select
            held_terminal = held_fd is not None and bool(select.select([held_fd],[],[],0)[0])
            stop = load(private/"stop-outcome.json")
            terminal = ci_terminal_values(unit,current,stop,props,process is not None and process.poll() is not None,
                process.returncode if process is not None else None,held_terminal,group_exists,populated)
            save(private/"root-terminal.json",{"unit":unit,"properties":props,"groupExists":group_exists,
                "populated":populated,"heldPidfdTerminal":held_terminal,"stopOutcome":stop,"terminal":terminal})
        except BaseException as exc:failure = (failure or "")+"; terminal metadata: "+str(exc)
        if held_fd is not None:os.close(held_fd)
        save(private/"consumer-terminal.json",{"terminal":terminal,"failure":failure,"current":current,"caps":CAPS})
    require(terminal and failure is None and time.monotonic_ns() < end_ns,"row HOLD unless own actual terminal proof")
    return 0


def ci_controlled(policy, current, private, args, row_start_ns):
    row_start = row_start_ns / 10**9
    # Own native controls before every worker/acquisition/materialization/SDK/product command.
    require(policy["caps"] == CAPS, "own02 caps, not producer caps")
    if os.name == "nt":
        policy = {**policy, "ciJobName":"Local\\execution02-ci-"+uuid.uuid4().hex}
    npm_links = locked_npm_bin_links()
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
        if os.name == "nt" and not args.ci_control_only:
            save(private/"context.json",current)
            command = [sys.executable,"-I","-B",str(Path(__file__).resolve()),"--ci","--ci-worker","--ci-rid","win-x64",
                "--ci-policy",str(args.ci_policy),"--ci-policy-sha256",args.ci_policy_sha256,
                "--ci-row-start",str(row_start_ns),"--ci-context",str(private/"context.json"),
                "--ci-context-sha256",sha(private/"context.json")]
        with (private/"worker.log").open("xb") as log:
            if args.ci_control_only:
                command = [sys.executable,"-I","-B","-c","import os,json;print(json.dumps({'sdkCommands':0,'pid':os.getpid()}))"]
            controller.start(command,env,log)
            save(private/"containment.json",{"caps":CAPS,"readback":controller.readback,"child":controller.child,
                 "launcherSha256":sha(__file__),"currentJob":current["job"],"rid":current["rid"]})
            if os.name == "nt" and not args.ci_control_only:
                caps, admission, ctx = windows_documents(policy,current,controller,private,row_start_ns,row_start_ns+620*10**9)
                save(private/"own-caps.json",caps);save(private/"consumer-admission.json",admission);save(private/"normal-context.json",ctx)
            controller.resume()
            while (code := controller.poll()) is None:
                require(time.monotonic()-row_start < 600, "remaining row work deadline")
                size1, logs1 = footprint(ROOT, ROOT, npm_links)
                size2, logs2 = footprint(private, private)
                sdk_scope = Path(os.environ["RUNNER_TEMP"])/("sdk11-normal-02-"+private.name)
                sdk_size, sdk_logs = footprint(sdk_scope,sdk_scope) if sdk_scope.exists() else (0,0)
                size2 += sdk_size; logs2 += sdk_logs
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

def prepare_ci_policy(current):
    """Own signed source + actual hosted metadata; no SDK or producer admission."""
    import shutil
    temp = Path(os.environ["RUNNER_TEMP"]).resolve()
    bootstrap = temp/("execution02-policy-"+uuid.uuid4().hex)
    bootstrap.mkdir(mode=0o700)
    def git(*argv):
        return subprocess.check_output(["git",*argv],cwd=ROOT,timeout=10)
    require(not git("status","--porcelain=v1","--untracked-files=all"), "own clean signed source required")
    require(git("rev-parse","HEAD").decode().strip() == current["source"]["commit"], "own observed source identity")
    pub = ROOT/"SIGNING-PUBLIC-KEY.pub"
    ssh = shutil.which("ssh-keygen")
    require(ssh and pub.is_file(), "existing source signature tooling missing")
    known = "SHA256:AgU5bZlJSjUu0KsWMmVEEr+BfXpcMVNroTA33bHcQdU"
    fingerprint = subprocess.check_output([ssh,"-lf",str(pub)],timeout=5,text=True)
    require(known in fingerprint, "known source signing fingerprint")
    signers = bootstrap/"allowed-signers"
    signers.write_bytes(b"pouriajamali "+pub.read_bytes().strip()+b"\n")
    signed = subprocess.run(["git","-c","gpg.ssh.allowedSignersFile="+str(signers),"verify-commit","HEAD"],
        cwd=ROOT,timeout=10,capture_output=True,text=True)
    require(signed.returncode == 0 and known in signed.stdout+signed.stderr, "own known-key source signature")
    table_path = ROOT/"tools/sdk11-own-source-pins.json"
    table = load(table_path)
    actual = {}
    for row in git("ls-tree","-r","-z","HEAD").split(b"\0"):
        if not row:continue
        meta,name = row.split(b"\t",1)
        mode,kind,blob = meta.decode().split()
        name = name.decode()
        require(kind == "blob" and mode in ("100644","100755"), "own source regular modes")
        if name != "tools/sdk11-own-source-pins.json":
            actual[name] = {"path":name,"mode":mode,"gitBlob":blob}
    expected = {row["path"]:row for row in table["sourcePins"]}
    require(actual == expected and len(expected) == len(table["sourcePins"]), "own exact full source table")
    for name,row in actual.items():
        raw = safe_path(ROOT/name,ROOT).read_bytes()
        require(hashlib.sha1(b"blob "+str(len(raw)).encode()+b"\0"+raw).hexdigest() == row["gitBlob"], "own working source bytes")
    for name, expected_hash in NORMAL_PINS.items():
        require(sha(ROOT/name) == expected_hash, "single immutable common source: "+name)
    rid = current["rid"]
    profile = ROOT/("tools/sdk11-own-windows-profile.json" if rid == "win-x64" else "tools/sdk11-own-profile.json")
    fact_path = ROOT/("tools/sdk11-normal/accepted-windows-fact.json" if rid == "win-x64" else "tools/sdk11-normal/accepted-linux-fact.json")
    fact = load(fact_path)
    node_candidates = []
    cache = Path(os.environ.get("RUNNER_TOOL_CACHE",str(temp/"no-toolcache")))
    pattern = "node/24.*/x64/node.exe" if os.name == "nt" else "node/24.*/x64/bin/node"
    node_candidates.extend(sorted(cache.glob(pattern),reverse=True))
    ambient = shutil.which("node")
    if ambient:node_candidates.append(Path(ambient))
    require(node_candidates and len(node_candidates) <= 32, "existing Node24 candidate metadata missing")
    # Actual v24 is checked inside the held worker before npm; no install/fallback.
    node = next((path.resolve() for path in node_candidates if path.is_file()),None)
    require(node is not None, "existing Node24 tool not present")
    npm_candidates = [node.parent/"node_modules/npm/bin/npm-cli.js",node.parent.parent/"lib/node_modules/npm/bin/npm-cli.js"]
    npm_cli = next((path.resolve() for path in npm_candidates if path.is_file()),None)
    require(npm_cli is not None, "existing Node npm CLI missing")
    def tool(name):
        path = shutil.which(name)
        require(path is not None, "existing tool missing: "+name)
        return Path(path).resolve()
    tools = {"node":node,"npmCli":npm_cli,"git":tool("git"),"pwsh":tool("pwsh")}
    contract = ROOT/"docs/SDK11-CONSUMER-CONTRACT.json"
    canonical_pins = hashlib.sha256(json.dumps(table["sourcePins"],sort_keys=True,separators=(",",":"),ensure_ascii=False).encode()).hexdigest()
    admission = {"schema":"sdk11-consumer-host-admission/v1","state":"ADMITTED_EXACT_SUPPORTED_HOST_CLASS","projectId":"02",
        "producerFactSha256":sha(fact_path),"admittedFor":{"hostClass":current["hostClass"],"rid":rid,"sdk":"11.0.100","runtime":"11.0.0",
            "memberManifestSha256":fact["tree"]["memberManifestSha256"],"contractSha256":sha(contract),"sourcePinTableSha256":canonical_pins,
            "controllerSha256":sha(__file__),"profileSha256":sha(profile)},"currentExecution":{},
        "identityRule":"QUALIFIED_ON_IS_HISTORICAL_PRODUCER_INSTANCE_CURRENT_CONSUMER_JOB_MAY_DIFFER"}
    directories = list(dict.fromkeys(str(path.parent) for name,path in tools.items() if name != "npmCli"))
    directories.extend([str(Path(os.environ["SystemRoot"])/"System32")] if os.name == "nt" else ["/usr/bin","/bin"])
    policy = {"schema":"execution02-own-source-bound-ci-policy/v1","state":"EXACT_CI_CONSUMER_ADMISSION","project":"02",
        "authority":"Direct owner existing02upgrade task; exact known-key signed own source and observed hosted instance. This does not fabricate a new coordinator approval or grant product/input PASS.",
        "contractSha256":M0,"designGateSha256":"9b3e0f376c5381b623f6a0f007bf6a6bb44f3dcbd1c2e4654de949a1eb97eec8",
        "consumerSource":current["source"],"controllerSha256":sha(__file__),"pythonSha256":sha(Path(sys.executable).resolve()),
        "consumerAdmission":admission,"acceptedProducerQualifiedOn":fact["qualifiedOn"],"caps":CAPS,
        "currentEvidenceBinding":"OWN_SUPERVISOR_BINDS_CURRENT_HELD_MAINPID_V1",
        "currentHostRules":{"imageOS":current["imageOS"],"imageVersions":[current["imageVersion"]],"osIdentities":[current["osIdentity"]]},
        "producerInterface":{"path":str(ROOT/"tools/dotnet11-host-qualification.schema.json"),"sha256":NORMAL_PINS["tools/dotnet11-host-qualification.schema.json"],"schemaId":"urn:pouria:dotnet11-host-qualification:v1"},
        "producerFact":{"path":str(fact_path),"sha256":sha(fact_path)},"ownContract":{"path":str(contract),"sha256":sha(contract)},
        "profile":{"path":str(profile),"sha256":sha(profile)},"sourcePinTable":{"path":str(table_path),"sha256":sha(table_path)},
        "tools":{name:{"path":str(path),"sha256":sha(path)} for name,path in tools.items()},"toolDirectories":directories,
        "sourceSignature":{"fingerprint":known,"verified":True},"ordinaryInputClosure":"REQUIRED_SEPARATE_REAL02INPUT_GATE_NOT_A_PRODUCER_FACT"}
    if os.name != "nt":
        policy["linuxStarterHashes"] = {name:sha(name) for name in ("/usr/bin/sudo","/usr/bin/systemd-run","/usr/bin/systemctl")}
    output = bootstrap/"own-policy.json"
    save(output,policy)
    return output,sha(output)

def ci_entry():
    original_start = time.monotonic_ns()
    require(sys.version_info[:2] >= (3,12), "preinstalled Python >=3.12 required; no install")
    p = argparse.ArgumentParser()
    p.add_argument("--ci", action="store_true")
    p.add_argument("--ci-worker", action="store_true")
    p.add_argument("--ci-stop-post", action="store_true")
    p.add_argument("--ci-control-only", action="store_true")
    p.add_argument("--ci-row-start", default="")
    p.add_argument("--ci-context", type=Path)
    p.add_argument("--ci-context-sha256")
    p.add_argument("--ci-unit", default="")
    p.add_argument("--ci-policy", type=Path)
    p.add_argument("--ci-policy-sha256")
    p.add_argument("--ci-rid", choices=("win-x64","linux-x64"), required=True)
    args = p.parse_args()
    if not args.ci_row_start:args.ci_row_start = str(original_start)
    observed = None
    if args.ci_policy is None and not args.ci_worker and not args.ci_stop_post:
        require(args.ci_policy_sha256 is None, "policy path and digest must be paired")
        observed = ci_observe(args.ci_rid)
        args.ci_policy,args.ci_policy_sha256 = prepare_ci_policy(observed)
    require(args.ci_policy is not None and args.ci_policy_sha256, "exact parent policy required")
    return ci_row(args, observed)

def local_stop_entry():
    import re
    from types import SimpleNamespace
    require(os.name != "nt" and len(sys.argv) == 5, "fixed local stop observer")
    context=Path(sys.argv[2]).resolve();expected=sys.argv[3];unit=sys.argv[4]
    require(context.is_relative_to(ROOT/"artifacts/local-service")
            and re.fullmatch(r"execution02-local-[a-z]+-[a-f0-9]{16}[.]service",unit), "owned local stop identity")
    current=load(context,expected)
    require(current.get("kind") == "LOCAL_PROJECT02" and current["profileSha256"] == sha(ROOT/"tools/sdk11-own-local-profile.json"), "local observer source/profile")
    return ci_stop_post(None,SimpleNamespace(ci_context=context,ci_context_sha256=expected,ci_unit=unit))

if __name__ == "__main__":
    try:
        sys.exit(local_stop_entry() if "--local-stop-post" in sys.argv else ci_entry() if "--ci" in sys.argv else main())
    except Hold as error:
        print(json.dumps({"status": "COMPLETED_INPUT_DENIAL", "reason": str(error)}))
        sys.exit(2)
