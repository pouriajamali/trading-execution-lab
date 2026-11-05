"""Finite launcher contract with a trusted local fake child, not an API/runtime demo."""
import argparse
import hashlib
import json
import os
from pathlib import Path
import subprocess
import sys


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--work", type=Path, required=True)
    args = parser.parse_args()
    args.work = args.work.resolve()
    args.work.mkdir(parents=True, exist_ok=False)
    launcher = Path(__file__).resolve().with_name("Start-OperatorPanel.ps1")
    # A secure interactive console cannot consume redirected stdin reliably.
    # For the standalone exit-code probe change ONLY Read-Host input acquisition
    # in a private source copy; the shipped launcher itself keeps secure prompting.
    source = launcher.read_text(encoding="utf-8")
    prompt = "$secureCode = Read-Host 'Choose an operator code for this run (16–128 characters)' -AsSecureString"
    assert source.count(prompt) == 1
    direct = args.work / "direct-with-prompt-stub.ps1"
    direct.write_text(source.replace(prompt,
        "$secureCode = ConvertTo-SecureString $env:LAUNCHER_PROBE_CODE -AsPlainText -Force"), encoding="utf-8")
    harness = args.work / "harness.ps1"
    harness.write_text(r'''
$variables = @('EXECUTION_LAB_PANEL', 'EXECUTION_LAB_PANEL_SEED_NEW', 'EXECUTION_LAB_DB', 'EXECUTION_LAB_KEY_BASE64', 'EXECUTION_LAB_OPERATOR_CODE')
foreach ($name in $variables) { [Environment]::SetEnvironmentVariable($name, 'original-test-value', 'Process') }
function Read-Host { ConvertTo-SecureString $env:LAUNCHER_PROBE_CODE -AsPlainText -Force }
$observedExit = 1
try {
    & $env:LAUNCHER_PROBE_SCRIPT -PublishedDirectory $env:LAUNCHER_PROBE_PUBLISH -Dotnet $env:LAUNCHER_PROBE_RUNTIME
    $observedExit = $LASTEXITCODE
} finally {
    $restored = @($variables | Where-Object { [Environment]::GetEnvironmentVariable($_, 'Process') -ne 'original-test-value' }).Count -eq 0
    [System.IO.File]::WriteAllText($env:LAUNCHER_PROBE_ENV_RECEIPT, ($restored | ConvertTo-Json))
}
exit $observedExit
''', encoding="utf-8")
    observations = []
    for name, child_exit, code in [("clean", 0, "SYNTHETIC-LOCAL-LAUNCHER-CODE"),
                                   ("failure", 17, "SYNTHETIC-LOCAL-LAUNCHER-CODE"),
                                   ("invalid-code", 0, "short")]:
        work = args.work / name
        work.mkdir()
        published = work / "published with spaces"
        published.mkdir()
        trace = work / "child.json"
        restored = work / "environment.json"
        # Python is the known test interpreter, not downloaded executable code.
        (published / "ExecutionLab.Api.dll").write_text('''
import os, json, pathlib, base64, sys
db = pathlib.Path(os.environ["EXECUTION_LAB_DB"])
db.write_text("owned disposable test data")
assert len(base64.b64decode(os.environ["EXECUTION_LAB_KEY_BASE64"])) == 32
assert os.environ["EXECUTION_LAB_OPERATOR_CODE"] == os.environ["LAUNCHER_PROBE_CODE"]
assert os.environ["EXECUTION_LAB_PANEL"] == "1"
assert os.environ["EXECUTION_LAB_PANEL_SEED_NEW"] == "1"
pathlib.Path(os.environ["LAUNCHER_PROBE_TRACE"]).write_text(json.dumps({"ownedDirectory":str(db.parent),"runOnlyConfigurationValid":True}))
sys.exit(int(os.environ["LAUNCHER_PROBE_EXIT"]))
''', encoding="utf-8")
        env = dict(os.environ, LAUNCHER_PROBE_SCRIPT=str(launcher), LAUNCHER_PROBE_PUBLISH=str(published),
                   LAUNCHER_PROBE_RUNTIME=sys.executable, LAUNCHER_PROBE_TRACE=str(trace),
                   LAUNCHER_PROBE_ENV_RECEIPT=str(restored), LAUNCHER_PROBE_EXIT=str(child_exit),
                   LAUNCHER_PROBE_CODE=code)
        result = subprocess.run(["pwsh", "-NoProfile", "-File", str(harness)], env=env,
                                capture_output=True, text=True, timeout=20)
        (work / "process.json").write_text(json.dumps({"exit": result.returncode,
            "stdout": result.stdout.replace(code, "<redacted-test-code>"),
            "stderr": result.stderr.replace(code, "<redacted-test-code>")}, indent=2), encoding="utf-8")
        assert json.loads(restored.read_text()) is True, name
        assert code not in result.stdout + result.stderr, "Operator code leaked to launcher output"
        if name == "invalid-code":
            assert result.returncode != 0 and not trace.exists()
        else:
            assert result.returncode == child_exit, (name, result.returncode, result.stderr)
            assert not Path(json.loads(trace.read_text())["ownedDirectory"]).exists(), "Owned disposable data retained"
            direct_result = subprocess.run(["pwsh", "-NoProfile", "-File", str(direct),
                "-PublishedDirectory", str(published), "-Dotnet", sys.executable], env=env,
                capture_output=True, text=True, timeout=20)
            (work / "direct-process.json").write_text(json.dumps({"exit": direct_result.returncode,
                "stdout": direct_result.stdout.replace(code, "<redacted-test-code>"),
                "stderr": direct_result.stderr.replace(code, "<redacted-test-code>")}, indent=2), encoding="utf-8")
            assert direct_result.returncode == child_exit, (name, "direct launcher exit", direct_result.returncode)
            assert code not in direct_result.stdout + direct_result.stderr
            assert not Path(json.loads(trace.read_text())["ownedDirectory"]).exists()
        observations.append({"case": name, "expectedChildExit": child_exit, "actualLauncherExit": result.returncode,
                             "environmentRestored": True, "ownedDirectoryCleaned": trace.exists()})
    receipt = {"status": "LAUNCHER_EXIT_ENVIRONMENT_AND_OWNED_CLEANUP_PASS", "cases": observations,
               "launcherSha256": hashlib.sha256(launcher.read_bytes()).hexdigest(),
               "scope": "Trusted fake Python child; environment check calls the original script with Read-Host mocked. Standalone exit check uses a copy with only Read-Host replaced; not an interactive console proof. Actual ASP.NET Core package is checked separately."}
    (args.work / "receipt.json").write_text(json.dumps(receipt, indent=2) + "\n", encoding="utf-8")
    print(json.dumps({"status": receipt["status"], "cases": len(observations)}))


if __name__ == "__main__":
    main()
