"""Inspect the two already-tested archives; never rebuild during aggregation."""
import argparse
import hashlib
import json
from pathlib import Path, PurePosixPath
import tarfile
import zipfile


def inspect_archive(path, commit, version, rid):
    payload = {}
    if path.suffix == ".zip":
        with zipfile.ZipFile(path) as archive:
            for info in archive.infolist():
                if not info.is_dir():
                    assert info.file_size <= 16 * 1024 * 1024
                    assert info.filename not in payload
                    payload[info.filename] = archive.read(info)
    else:
        with tarfile.open(path, "r:gz") as archive:
            for info in archive:
                assert info.isdir() or info.isfile(), "No links or special entries allowed"
                if info.isfile():
                    assert info.size <= 16 * 1024 * 1024
                    assert info.name not in payload
                    payload[info.name] = archive.extractfile(info).read()
    assert len(payload) <= 256 and sum(map(len, payload.values())) <= 64 * 1024 * 1024
    for name in payload:
        assert not PurePosixPath(name).is_absolute() and ".." not in PurePosixPath(name).parts
    roots = {PurePosixPath(name).parts[0] for name in payload}
    assert len(roots) == 1
    prefix = roots.pop() + "/"
    assert all(name.startswith(prefix) for name in payload)
    files = {name[len(prefix):]: value for name, value in payload.items()}
    manifest = json.loads(files.pop("BUILD-MANIFEST.json"))
    assert (manifest["sourceCommit"], manifest["version"], manifest["rid"], manifest["selfContained"]) == (commit, version, rid, False)
    assert set(files) == {item["path"] for item in manifest["files"]}
    for item in manifest["files"]:
        raw = files[item["path"]]
        assert len(raw) == item["bytes"] and hashlib.sha256(raw).hexdigest() == item["sha256"]
    assert commit.encode("ascii") in files["ExecutionLab.Api.dll"]
    assert {"LICENSE", "README.md", "Start-OperatorPanel.ps1", "THIRD-PARTY-DEPENDENCIES.json"}.issubset(files)
    assert not any(name.lower().endswith((".pdb", ".sqlite")) for name in files)
    return {"name": path.name, "sha256": hashlib.sha256(path.read_bytes()).hexdigest(), "bytes": path.stat().st_size,
            "rid": rid, "sourceCommit": commit, "sourceTree": manifest["sourceTree"], "payloadFiles": len(files)}


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--directory", type=Path, required=True)
    parser.add_argument("--commit", required=True)
    parser.add_argument("--tag", required=True)
    args = parser.parse_args()
    version = args.tag.removeprefix("v")
    names = {"win-x64": f"trading-execution-lab-{args.tag}-win-x64.zip",
             "linux-x64": f"trading-execution-lab-{args.tag}-linux-x64.tar.gz"}
    assert {p.name for p in args.directory.iterdir()} == set(names.values())
    results = [inspect_archive(args.directory / name, args.commit, version, rid) for rid, name in names.items()]
    assert results[0]["sourceTree"] == results[1]["sourceTree"]
    print(json.dumps({"status": "BOTH_EXECUTED_ARCHIVES_VERIFIED_NO_REBUILD", "archives": results}))


if __name__ == "__main__":
    main()
