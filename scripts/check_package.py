"""Bounded, real loopback ASP.NET Core + SQLite checks on an extracted package.

Needs the matching installed ASP.NET Core .NET 10 runtime, Python and an idle
127.0.0.1:5087. Never contacts a broker or uses user/market data. No benchmark.
"""
import argparse
import base64
import hashlib
import hmac
import http.client
import json
import os
from pathlib import Path
import re
import secrets
import socket
import sqlite3
import subprocess
import time


def digest(path):
    return hashlib.sha256(path.read_bytes()).hexdigest()


def verify_manifest(package, commit):
    manifest = json.loads((package / "BUILD-MANIFEST.json").read_text(encoding="utf-8"))
    assert manifest["sourceCommit"] == commit
    assert manifest["selfContained"] is False
    assert manifest["rid"] == ("win-x64" if os.name == "nt" else "linux-x64")
    inventory = {item["path"]: item for item in manifest["files"]}
    actual = {p.relative_to(package).as_posix(): p for p in package.rglob("*") if p.is_file()}
    assert set(actual) == set(inventory) | {"BUILD-MANIFEST.json"}
    for name, item in inventory.items():
        assert actual[name].stat().st_size == item["bytes"] and digest(actual[name]) == item["sha256"], name
    assert not any(name.lower().endswith((".pdb", ".sqlite")) or "testhost" in name.lower() for name in actual)
    return manifest


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--package", type=Path, required=True)
    parser.add_argument("--work", type=Path, required=True)
    parser.add_argument("--dotnet", default="dotnet")
    parser.add_argument("--commit")
    args = parser.parse_args()
    package = args.package.resolve()
    work = args.work.resolve()
    work.mkdir(parents=True, exist_ok=False)
    manifest = verify_manifest(package, args.commit) if args.commit else None
    config = json.loads((package / "ExecutionLab.Api.runtimeconfig.json").read_text())["runtimeOptions"]
    assert "includedFrameworks" not in config
    assert {f["name"] for f in config["frameworks"]} == {"Microsoft.NETCore.App", "Microsoft.AspNetCore.App"}
    assert all(f["version"].startswith("10.") for f in config["frameworks"])
    with socket.socket() as check:
        check.bind(("127.0.0.1", 5087))  # Refuse to disturb an existing service.
    key = secrets.token_bytes(32)
    key_text = base64.b64encode(key).decode()
    code = secrets.token_urlsafe(24)
    private_values = [key_text, code]
    database = work / "synthetic.sqlite"
    env = {k: v for k, v in os.environ.items() if not k.upper().startswith(("EXECUTION_LAB_", "KESTREL__", "ASPNETCORE_"))
           and k.upper() not in {"DOTNET_STARTUP_HOOKS", "DOTNET_ENVIRONMENT"}}
    env.update(EXECUTION_LAB_KEY_BASE64=key_text, EXECUTION_LAB_OPERATOR_CODE=code,
               EXECUTION_LAB_PANEL="1", EXECUTION_LAB_PANEL_SEED_NEW="1", EXECUTION_LAB_DB=str(database),
               ASPNETCORE_ENVIRONMENT="Production", DOTNET_ENVIRONMENT="Production")
    observations = []
    processes = []

    def request(path, body=None, token=None, idem=None, host=None):
        headers = {"Content-Type": "application/json"} if body is not None else {}
        if token: headers["Authorization"] = "Bearer " + token
        if idem: headers["Idempotency-Key"] = idem
        if host: headers["Host"] = host
        connection = http.client.HTTPConnection("127.0.0.1", 5087, timeout=3)
        connection.request("POST" if body is not None else "GET", path,
                           None if body is None else json.dumps(body), headers)
        response = connection.getresponse()
        payload = response.read(1_048_577)
        assert len(payload) <= 1_048_576
        result = response.status, dict(response.getheaders()), payload
        connection.close()
        return result

    def status_case(name, expected, path, **kwargs):
        status, headers, payload = request(path, **kwargs)
        assert status == expected, (name, status, expected)
        observations.append({"case": name, "http": status})
        return headers, payload

    def start(name, overrides=None, serve=True):
        log = (work / (name + ".log")).open("wb")
        child_env = dict(env, **(overrides or {}))
        process = subprocess.Popen([args.dotnet, str(package / "ExecutionLab.Api.dll")],
                                   cwd=package, env=child_env, stdout=log, stderr=subprocess.STDOUT)
        processes.append((process, log))
        if serve:
            deadline = time.monotonic() + 12
            while time.monotonic() < deadline:
                assert process.poll() is None, (name, "host exited before readiness")
                try:
                    if request("/panel/")[0] == 200: return process
                except (OSError, http.client.HTTPException): pass
                time.sleep(.05)
            raise TimeoutError("Finite loopback host readiness budget exhausted")
        process.wait(timeout=12)
        log.flush()
        assert process.returncode != 0, name
        return process

    def stop(process):
        # The harness owns this exact child. This is a process restart test, not
        # a graceful interactive-console or power-loss durability claim.
        if process.poll() is None:
            process.terminate()
            try: process.wait(timeout=5)
            except subprocess.TimeoutExpired:
                process.kill(); process.wait(timeout=3)

    def jwt(subject="package-check", role="operator", signing_key=key):
        def part(value):
            return base64.urlsafe_b64encode(json.dumps(value, separators=(",", ":")).encode()).rstrip(b"=")
        now = int(time.time())
        message = part({"alg": "HS256", "typ": "JWT"}) + b"." + part({
            "iss": "execution-lab-local", "aud": "execution-lab-control", "sub": subject,
            "role": role, "nbf": now - 1, "exp": now + 120})
        token = (message + b"." + base64.urlsafe_b64encode(hmac.digest(signing_key, message, "sha256")).rstrip(b"=")).decode()
        private_values.append(token)
        return token

    try:
        host = start("seeded-host")
        _, html = status_case("panel HTML", 200, "/panel/")
        assets = re.findall(rb'(?:src|href)="(/panel/assets/[^\"]+)"', html)
        assert len(assets) >= 2
        for asset in assets: status_case("built static asset", 200, asset.decode())
        status_case("unauthenticated state", 401, "/panel/api/state")
        headers, _ = status_case("wrong local operator code", 401, "/panel/api/session", body={"code": "wrong-synthetic-code"})
        assert headers.get("Cache-Control") == "no-store"
        headers, login = status_case("local operator login", 200, "/panel/api/session", body={"code": code})
        assert headers.get("Cache-Control") == "no-store"
        token = json.loads(login)["token"]; private_values.append(token)
        headers, raw = status_case("seeded authenticated state", 200, "/panel/api/state", token=token)
        assert headers.get("Cache-Control") == "no-store"
        state = json.loads(raw)
        assert (state["position"], state["pending"], state["exposure"], state["sequence"]) == (4, 3, 7, 2)
        assert "frame-ancestors 'none'" in headers["Content-Security-Policy"]
        status_case("bad Host header", 400, "/panel/api/state", token=token, host="external.example")
        status_case("reader cannot mutate", 403, "/reservations", body={"orderId": "reader", "quantity": 1}, token=jwt(role="reader"), idem="reader")
        status_case("empty subject cannot mutate", 403, "/reservations", body={"orderId": "empty", "quantity": 1}, token=jwt(subject=""), idem="empty")
        status_case("invalid signature cannot mutate", 401, "/reservations", body={"orderId": "invalid", "quantity": 1}, token=jwt(signing_key=secrets.token_bytes(32)), idem="invalid")
        command = {"orderId": "package-order", "quantity": 2}
        _, raw = status_case("accepted reservation", 200, "/reservations", body=command, token=token, idem="package-request")
        accepted = json.loads(raw)
        assert accepted == {"accepted": True, "reason": "Applied", "sequence": 3, "exposure": 9, "replayed": False}
        _, raw = status_case("same-key original receipt", 200, "/reservations", body=command, token=token, idem="package-request")
        assert json.loads(raw) == dict(accepted, replayed=True)
        status_case("same-key changed-content conflict", 409, "/reservations", body=dict(command, quantity=1), token=token, idem="package-request")
        _, raw = status_case("risk denial commits receipt", 200, "/reservations", body={"orderId": "denied-order", "quantity": 2}, token=token, idem="denied-request")
        assert json.loads(raw) == {"accepted": False, "reason": "Exposure limit", "sequence": 4, "exposure": 9, "replayed": False}
        status_case("invalid quantity no write", 400, "/reservations", body={"orderId": "invalid", "quantity": -1}, token=token, idem="negative")
        status_case("out-of-Int64 body no write", 400, "/reservations", body={"orderId": "invalid", "quantity": 9223372036854775808}, token=token, idem="unrepresentable")
        stop(host)
        with sqlite3.connect(database) as db:
            assert db.execute("SELECT count(*) FROM receipts").fetchone()[0] == 4
            assert db.execute("SELECT count(*) FROM outbox").fetchone()[0] == 4
            stored = json.loads(db.execute("SELECT state FROM gate WHERE id=1").fetchone()[0])
            assert stored["Sequence"] == 4
            assert sum(x["Remaining"] for x in stored["Orders"].values()) + stored["Position"] == 9
        host = start("reopened-host", {"EXECUTION_LAB_PANEL_SEED_NEW": "0"})
        _, raw = status_case("reopen original receipt", 200, "/reservations", body=command, token=token, idem="package-request")
        assert json.loads(raw) == dict(accepted, replayed=True)
        _, raw = status_case("reopen current state separate", 200, "/panel/api/state", token=token)
        assert json.loads(raw)["sequence"] == 4 and json.loads(raw)["exposure"] == 9
        stop(host)
        before = digest(database)
        start("refuse-existing-seed", serve=False)
        assert digest(database) == before
        guard_db = work / "endpoint-guard.sqlite"
        start("refuse-configured-endpoint", {"Kestrel__Endpoints__Unexpected__Url": "http://127.0.0.1:5088",
              "EXECUTION_LAB_DB": str(guard_db)}, serve=False)
        assert not guard_db.exists()
        observations.extend([{"case": "atomic SQLite state/receipt/outbox on disk", "result": "PASS"},
                             {"case": "existing DB not reseeded", "result": "PASS"},
                             {"case": "configured endpoints rejected before DB", "result": "PASS"}])
    finally:
        for process, log in processes:
            stop(process); log.close()
    for log in work.glob("*.log"):
        text = log.read_text(encoding="utf-8", errors="replace")
        assert not any(value in text for value in private_values), "Secret value leaked into host log"
    receipt = {"status": "ACTUAL_FRAMEWORK_DEPENDENT_PACKAGE_HTTP_SQLITE_PASS", "sourceCommit": args.commit,
               "packageManifest": manifest, "checks": observations, "ownedProcesses": len(processes),
               "apiAssemblySha256": digest(package / "ExecutionLab.Api.dll"),
               "runtimeInventory": subprocess.check_output([args.dotnet, "--list-runtimes"], text=True).splitlines(),
               "scope": "Actual DLL on matching installed ASP.NET Core runtime; host may have SDK. Four owned processes, bounded HTTP/readiness, process reopen, no benchmark/power-loss/graceful-console claim. Random keys/code/JWT never written to receipt/log."}
    (work / "receipt.json").write_text(json.dumps(receipt, indent=2) + "\n", encoding="utf-8")
    print(json.dumps({"status": receipt["status"], "checks": len(observations), "processes": len(processes)}))


if __name__ == "__main__":
    main()
