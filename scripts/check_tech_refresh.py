"""Finite metadata-denial checks; no SDK invocation or wrapper child launch."""
import argparse
import copy
import hashlib
import importlib.util
import json
from pathlib import Path
from types import SimpleNamespace

def main():
    p = argparse.ArgumentParser()
    for name in ("binding", "binding-sha256", "work"):
        p.add_argument("--" + name, required=True)
    a = p.parse_args()
    raw = Path(a.binding).read_bytes()
    if hashlib.sha256(raw).hexdigest() != a.binding_sha256:
        raise RuntimeError("unbound guard input")
    original = json.loads(raw.decode("utf-8-sig"))
    source = Path(__file__).with_name("run_bounded.py")
    spec = importlib.util.spec_from_file_location("execution02guard", source)
    guard = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(guard)  # Definitions only; no Job/cgroup/controller is constructed.
    cases = [
        ("wrong-project", lambda b: b.update(project="06"), "wrong project/schema"),
        ("wrong-schema", lambda b: b.update(schema="foreign"), "wrong project/schema"),
        ("wrong-rid", lambda b: b.update(rid="foreign"), "RID mismatch"),
        ("wrong-contract", lambda b: b.update(contractSha256="tampered"), "authority identity"),
        ("wrong-approval", lambda b: b.update(approvalSha256="tampered"), "authority identity"),
        ("wrong-baseline", lambda b: b.update(baseCommit="tampered"), "authority identity"),
        ("cap-memory", lambda b: b["caps"].update(memoryBytes=1), "fixed profile mismatch"),
        ("cap-cpu", lambda b: b["caps"].update(cpuCores=3), "fixed profile mismatch"),
        ("cap-tasks", lambda b: b["caps"].update(tasks=128), "fixed profile mismatch"),
        ("cap-disk", lambda b: b["caps"].update(workspaceBytes=1), "fixed profile mismatch"),
        ("deadline", lambda b: b["phaseDeadlines"].update(csharp=481), "fixed profile mismatch"),
        ("foreign-checkout", lambda b: b.update(checkout=str(Path(a.work))), "wrong private checkout"),
        ("wrong-launcher", lambda b: b.update(launcherSha256="tampered"), "launcher identity"),
        ("empty-source", lambda b: b.update(sourceFiles=[]), "source inventory bounds"),
        ("duplicate-source", lambda b: b["sourceFiles"].append(b["sourceFiles"][0]), "incomplete/duplicate source inventory"),
        ("wrong-python", lambda b: b.update(pythonSha256="tampered"), "bootstrap interpreter identity"),
        ("wrong-mode", lambda b: b.update(mode="METADATA_READY"), "target execution not admitted"),
        ("wrong-sdk-version", lambda b: b.update(sdkVersion="foreign"), "SDK handoff identity"),
        ("wrong-sdk-digest", lambda b: b["sdkHandoff"].update(sha256="tampered"), "SDK handoff identity"),
        ("wrong-critical-member", lambda b: b["sdkHandoff"]["criticalFiles"][0].update(sha256="tampered"), "SDK critical member mismatch"),
    ]
    results = []
    for name, mutate, expected in cases:
        candidate = copy.deepcopy(original)
        mutate(candidate)
        path = Path(a.work) / (name + ".json")
        with path.open("x", encoding="utf-8") as stream:
            json.dump(candidate, stream)
        digest = hashlib.sha256(path.read_bytes()).hexdigest()
        try:
            guard.binding(SimpleNamespace(binding=path, binding_sha256=digest, phase="restoreAudit"))
        except guard.Hold as denial:
            if str(denial) != expected:
                raise RuntimeError("different causal rejection: " + name) from denial
        else:
            raise RuntimeError("candidate not rejected: " + name)
        results.append({"case": name, "status": "COMPLETED_NAMED_INPUT_DENIAL"})
    with (Path(a.work) / "guard-receipt.json").open("x", encoding="utf-8") as stream:
        json.dump({"status": "INPUT_DENIAL_CHECKS_COMPLETED", "cases": results,
                   "scope": "Metadata guards only; no SDK, kernel-control or malformed-archive claim."}, stream, indent=2)

# Inert supported-CI amendment: data validation only; never grants a local SDK route.
CI_HOSTS = {"win-x64": "GitHubHostedWindowsServer2025x64", "linux-x64": "GitHubHostedUbuntu24.04x64"}
def supported_ci_handshake(policy, fact, current, own):
    def deny(ok, why):
        if not ok:
            raise RuntimeError("CI_HOST_DENIED:" + why)
    interface = policy["producerInterface"]
    deny(interface["schemaId"] == "urn:pouria:dotnet11-host-qualification:v1"
         and interface["sha256"] == "63e04fa5d270c87b93e6e1f4c38bfbcf336b950b39fe1854dc4e514f0661f14c", "canonical-source-interface")
    shared = json.loads(Path(interface["path"]).read_text())
    deny(set(fact) == set(shared["required"]), "canonical-fact-fields")
    admission = policy["consumerAdmission"]
    deny(set(admission) == {"schema","state","projectId","producerFactSha256","admittedFor","currentExecution","identityRule"}
         and admission["schema"] == "sdk11-consumer-host-admission/v1"
         and admission["state"] == "ADMITTED_EXACT_SUPPORTED_HOST_CLASS" and admission["projectId"] == "02", "consumer-definition")
    deny(policy["state"] == "EXACT_CI_CONSUMER_ADMISSION" and policy["project"] == "02", "policy")
    deny(policy["contractSha256"] == "58e787ccf3e9e65b063d8bccd76d2b8332f106b9d4268cf66644a7af32f22a83"
         and policy["designGateSha256"] == "9b3e0f376c5381b623f6a0f007bf6a6bb44f3dcbd1c2e4654de949a1eb97eec8", "contract")
    rid = current["rid"]
    kinds = {"win-x64":"WindowsCIServer2025RID","linux-x64":"LinuxCIUbuntu24RID"}
    deny(rid in CI_HOSTS and current["hostClass"] == CI_HOSTS[rid], "current-host")
    deny(current["runnerEnvironment"] == "github-hosted" and current["isContainer"] is False, "hosted-vm")
    deny(current["source"] == policy["consumerSource"] and current["source"]["dirty"] is False, "source")
    deny(fact["schema"] == "sdk11-host-qualification/v1" and fact["factType"] == kinds[rid]
         and fact["outcome"] == "NATIVE_HOST_QUALIFICATION_OBSERVED", "producer-state")
    q, admitted, execution = fact["qualifiedOn"], admission["admittedFor"], admission["currentExecution"]
    definition = shared["$defs"]["consumerAdmission"]
    deny(set(q) == set(shared["properties"]["qualifiedOn"]["required"])
         and set(admitted) == set(definition["properties"]["admittedFor"]["required"])
         and set(execution) == set(definition["properties"]["currentExecution"]["required"]), "canonical-nested-fields")
    deny(q["repository"] == "pouriajamali/data-admission-gate" and q["job"] == "verify"
         and q == policy["acceptedProducerQualifiedOn"], "historical-producer-run-job")
    deny(admission["producerFactSha256"] == policy["producerFact"]["sha256"], "fact-digest")
    deny(fact["source"]["schemaSha256"] == interface["sha256"] and fact["terminal"]["workerExitCode"] == 0
         and fact["terminal"]["ownedPopulation"] == 0 and fact["terminal"]["supervisorObservedTerminal"] is True
         and fact["terminal"]["typedStopResult"] == "success", "accepted-producer-terminal-schema")
    deny(fact["toolchain"] == {"sdk":"11.0.100","runtime":"11.0.0","framework":"net11.0","language":"15.0"}, "toolchain")
    deny(q["hostClass"] == admitted["hostClass"] == current["hostClass"]
         and admitted["rid"] == q["rid"] == rid and admitted["sdk"] == "11.0.100"
         and admitted["runtime"] == "11.0.0", "admitted-host")
    deny(admitted["memberManifestSha256"] == fact["tree"]["memberManifestSha256"]
         and admitted["contractSha256"] == hashlib.sha256(Path(policy["ownContract"]["path"]).read_bytes()).hexdigest()
         and admitted["sourcePinTableSha256"] == own["sourcePinTableSha256"]
         and admitted["controllerSha256"] == own["controllerSha256"]
         and admitted["profileSha256"] == own["profileSha256"], "own-source-profile-member")
    image = policy["currentHostRules"]
    deny(current["imageOS"] == image["imageOS"] and current["imageVersion"] in image["imageVersions"]
         and current["osIdentity"] in image["osIdentities"], "image-os-version")
    deny(execution["runId"] == current["job"]["runId"] and execution["job"] == current["job"]["jobKey"]
         and execution["attempt"] == current["job"]["attempt"] and execution["instanceId"] == current["instanceId"]
         and execution["ownCapsEvidenceSha256"] == own["capsEvidenceSha256"], "own-current-instance")
    deny(admission["identityRule"] == "QUALIFIED_ON_IS_HISTORICAL_PRODUCER_INSTANCE_CURRENT_CONSUMER_JOB_MAY_DIFFER", "identity-rule")
    # qualifiedOn.runId/job are compared only with accepted producer history, never currentExecution.
    deny(own["currentJob"] == current["job"] and own["rid"] == rid and own["caps"] == policy["caps"]
         and own["heldBeforeResume"] is True, "own-controls")
    if rid == "linux-x64":
        deny(current["uid"] > 0 and current["gid"] > 0 and own["uid"] == current["uid"]
             and own["gid"] == current["gid"], "nonroot-worker")
    return {"producerQualifiedOn":q,"consumerCurrentJob":current["job"],"admittedFor":admitted,
            "consumerDefinition":"urn:pouria:dotnet11-host-qualification:v1#/$defs/consumerAdmission",
            "producerFactSha256":admission["producerFactSha256"],"rid":rid}

if __name__ == "__main__":
    main()
