"""Controlled local host checks; no real runtime, interactive-console or UI proof."""
import argparse
import hashlib
import json
import os
from pathlib import Path
import shlex
import subprocess
import sys


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--work", type=Path, required=True)
    parser.add_argument("--launcher", type=Path, help="Check an extracted package's launcher instead of the source copy")
    args = parser.parse_args()
    root = args.work.resolve()
    root.mkdir(parents=True, exist_ok=False)
    launcher = (args.launcher or Path(__file__).resolve().with_name("Start-OperatorPanel.ps1")).resolve()
    source = launcher.read_text(encoding="utf-8")
    prompt = "$secureCode = Read-Host 'Choose an operator code for this run (16–128 characters)' -AsSecureString"
    assert source.count(prompt) == 1
    direct = root / "direct-with-prompt-stub.ps1"
    direct.write_text(source.replace(prompt,
        "[IO.File]::WriteAllText($env:LAUNCHER_PROBE_PROMPT, 'prompt')\n"
        "$secureCode = ConvertTo-SecureString $env:LAUNCHER_PROBE_CODE -AsPlainText -Force"), encoding="utf-8")
    fake = root / "controlled host.py"
    fake.write_text('''import os,sys,json,subprocess
args=sys.argv[1:]
with open(os.environ['LAUNCHER_PROBE_SEQUENCE'],'a',encoding='utf-8') as f:
 f.write(json.dumps({'args':args,'language':os.environ.get('DOTNET_CLI_UI_LANGUAGE')})+'\\n')
if args==['--info']:
 print('Host:\\n  Version: 10.0.14\\n  Architecture: '+os.environ['LAUNCHER_PROBE_ARCH']+'\\n\\nOther architectures found:\\n  x64')
 sys.exit(int(os.environ.get('LAUNCHER_PROBE_INFO_EXIT','0')))
if args==['--list-runtimes']:
 print(os.environ['LAUNCHER_PROBE_FRAMEWORKS'])
 sys.exit(int(os.environ.get('LAUNCHER_PROBE_LIST_EXIT','0')))
sys.exit(subprocess.call([sys.executable,*args]))
''', encoding="utf-8")
    host = root / ("selected host.cmd" if os.name == "nt" else "selected host")
    if os.name == "nt":
        host.write_text(f'@"{sys.executable}" "{fake}" %*\n', encoding="utf-8")
    else:
        host.write_text(f'#!/bin/sh\nexec {shlex.quote(sys.executable)} {shlex.quote(str(fake))} "$@"\n', encoding="utf-8")
        host.chmod(0o700)
    harness = root / "harness.ps1"
    harness.write_text(r'''
$variables = @('EXECUTION_LAB_PANEL', 'EXECUTION_LAB_PANEL_SEED_NEW', 'EXECUTION_LAB_DB', 'EXECUTION_LAB_KEY_BASE64', 'EXECUTION_LAB_OPERATOR_CODE', 'DOTNET_CLI_UI_LANGUAGE')
foreach ($name in $variables) { [Environment]::SetEnvironmentVariable($name, 'original-test-value', 'Process') }
function Read-Host {
    [IO.File]::WriteAllText($env:LAUNCHER_PROBE_PROMPT, 'prompt')
    ConvertTo-SecureString $env:LAUNCHER_PROBE_CODE -AsPlainText -Force
}
$observedExit = 1
try {
    & $env:LAUNCHER_PROBE_SCRIPT -PublishedDirectory $env:LAUNCHER_PROBE_PUBLISH -Dotnet $env:LAUNCHER_PROBE_RUNTIME
    $observedExit = $LASTEXITCODE
} finally {
    $restored = @($variables | Where-Object { [Environment]::GetEnvironmentVariable($_, 'Process') -ne 'original-test-value' }).Count -eq 0
    [IO.File]::WriteAllText($env:LAUNCHER_PROBE_ENV_RECEIPT, ($restored | ConvertTo-Json))
}
exit $observedExit
''', encoding="utf-8")
    core = "Microsoft.NETCore.App 10.0.14 [controlled path with spaces]"
    def asp(patch):
        return f"Microsoft.AspNetCore.App 10.0.{patch} [controlled path with spaces]"
    good = core + "\n" + asp(14)
    cases = [
        ("clean", good, "x64", True, 0, "valid", {}),
        ("failure", good, "x64", True, 17, "valid", {}),
        ("invalid-code", good, "x64", True, 0, "short", {}),
        ("missing-asp", core, "x64", False, 0, "valid", {}),
        ("below-floor", core+"\n"+asp(13), "x64", False, 0, "valid", {}),
        ("later-patch", core+"\n"+asp(15), "x64", True, 0, "valid", {}),
        ("other-major", core+"\nMicrosoft.AspNetCore.App 11.0.14 [path]", "x64", False, 0, "valid", {}),
        ("other-minor", core+"\nMicrosoft.AspNetCore.App 10.1.14 [path]", "x64", False, 0, "valid", {}),
        ("prerelease", core+"\n"+asp("14-preview.1"), "x64", False, 0, "valid", {}),
        ("x86-host", good, "x86", False, 0, "valid", {}),
        ("arm-host", good, "arm64", False, 0, "valid", {}),
        ("missing-core", asp(14), "x64", False, 0, "valid", {}),
        ("core-below-floor", "Microsoft.NETCore.App 10.0.13 [path]\n"+asp(14), "x64", False, 0, "valid", {}),
        ("info-failure", good, "x64", False, 0, "valid", {"LAUNCHER_PROBE_INFO_EXIT":"9"}),
        ("list-failure", good, "x64", False, 0, "valid", {"LAUNCHER_PROBE_LIST_EXIT":"9"}),
        ("missing-host", good, "x64", False, 0, "valid", {"LAUNCHER_PROBE_RUNTIME":str(root/"absent host")}),
    ]
    observations = []
    for name, frameworks, arch, compatible, child_exit, code_kind, extra in cases:
        work = root / name
        work.mkdir()
        published = work / "published with spaces"
        published.mkdir()
        temp = work / "owned temp"
        temp.mkdir()
        trace, restored, prompted, sequence = [work / x for x in ("child.json","environment.json","prompt.txt","sequence.jsonl")]
        code = "short" if code_kind == "short" else "SYNTHETIC-LOCAL-LAUNCHER-CODE"
        (published/"ExecutionLab.Api.dll").write_text('''import os,json,pathlib,base64,sys
db=pathlib.Path(os.environ['EXECUTION_LAB_DB']);db.write_text('owned disposable test data')
assert len(base64.b64decode(os.environ['EXECUTION_LAB_KEY_BASE64']))==32
assert os.environ['EXECUTION_LAB_OPERATOR_CODE']==os.environ['LAUNCHER_PROBE_CODE']
assert os.environ['EXECUTION_LAB_PANEL']==os.environ['EXECUTION_LAB_PANEL_SEED_NEW']=='1'
pathlib.Path(os.environ['LAUNCHER_PROBE_TRACE']).write_text(json.dumps({'ownedDirectory':str(db.parent)}))
sys.exit(int(os.environ['LAUNCHER_PROBE_EXIT']))
''', encoding="utf-8")
        env = dict(os.environ, LAUNCHER_PROBE_SCRIPT=str(launcher), LAUNCHER_PROBE_PUBLISH=str(published),
            LAUNCHER_PROBE_RUNTIME=str(host), LAUNCHER_PROBE_TRACE=str(trace), LAUNCHER_PROBE_PROMPT=str(prompted),
            LAUNCHER_PROBE_SEQUENCE=str(sequence), LAUNCHER_PROBE_ENV_RECEIPT=str(restored),
            LAUNCHER_PROBE_EXIT=str(child_exit), LAUNCHER_PROBE_CODE=code, LAUNCHER_PROBE_ARCH=arch,
            LAUNCHER_PROBE_FRAMEWORKS=frameworks, TEMP=str(temp), TMP=str(temp), TMPDIR=str(temp))
        env.update(extra)
        for mode in ("harness","standalone"):
            if mode == "harness":
                command=["pwsh","-NoProfile","-File",str(harness)]
            else:
                env["DOTNET_CLI_UI_LANGUAGE"]="original-test-value"
                command=["pwsh","-NoProfile","-File",str(direct),"-PublishedDirectory",str(published),"-Dotnet",env["LAUNCHER_PROBE_RUNTIME"]]
            result=subprocess.run(command,env=env,capture_output=True,text=True,timeout=20)
            (work/(mode+".json")).write_text(json.dumps({"command":command,"exit":result.returncode,
                "stdout":result.stdout.replace(code,"<redacted-test-code>"),
                "stderr":result.stderr.replace(code,"<redacted-test-code>")},indent=2),encoding="utf-8")
            assert code not in result.stdout+result.stderr, name
            if mode == "harness":
                assert json.loads(restored.read_text()) is True, (name,"environment not restored")
            if not compatible:
                assert result.returncode != 0 and not prompted.exists() and not trace.exists(), (name,mode,"preflight must fail before prompt/child")
                assert not list(temp.iterdir()), (name,"temporary state before failed preflight")
                assert all(x in result.stderr for x in ("ASP.NET Core","10.0.14","x64")), (name,"actionable prerequisite message")
            elif code_kind == "short":
                assert result.returncode != 0 and prompted.exists() and not trace.exists()
                assert not list(temp.iterdir())
            else:
                assert result.returncode == child_exit, (name,mode,result.stderr)
                assert prompted.exists() and trace.exists()
                assert not Path(json.loads(trace.read_text())["ownedDirectory"]).exists(), (name,"owned data retained")
        if sequence.exists():
            probes=[json.loads(line) for line in sequence.read_text().splitlines()]
            assert all(p["language"]=="en-US" for p in probes if p["args"][0].startswith("--")), name
        observations.append({"case":name,"compatible":compatible,"bothModesPassed":True})
    receipt={"status":"LAUNCHER_PREFLIGHT_EXIT_ENVIRONMENT_AND_OWNED_CLEANUP_PASS","cases":observations,
        "launcherSha256":hashlib.sha256(launcher.read_bytes()).hexdigest(),
        "scope":"Controlled local host outputs, synthetic child and mocked secure input. Standalone copy replaces input only. No real runtime compatibility, interactive console or browser proof."}
    (root/"receipt.json").write_text(json.dumps(receipt,indent=2)+"\n",encoding="utf-8")
    print(json.dumps({"status":receipt["status"],"cases":len(observations)}))


if __name__ == "__main__":
    main()
