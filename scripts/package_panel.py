"""Build a clean exact-commit, framework-dependent package on its matching OS."""
import argparse
import hashlib
import json
import os
from pathlib import Path
import platform
import re
import shutil
import subprocess
import tarfile
import xml.etree.ElementTree as ET
import zipfile


ROOT = Path(__file__).resolve().parents[1]


def sha(path):
    return hashlib.sha256(path.read_bytes()).hexdigest()


def git(*args):
    return subprocess.check_output(["git", "-C", str(ROOT), *args], text=True).strip()


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--work", type=Path, required=True)
    parser.add_argument("--out", type=Path, required=True)
    parser.add_argument("--rid", choices=["win-x64", "linux-x64"], required=True)
    parser.add_argument("--commit", required=True)
    parser.add_argument("--dotnet", default="dotnet")
    parser.add_argument("--nuget-source")
    args = parser.parse_args()
    assert platform.machine().lower() in {"amd64", "x86_64"}
    assert args.rid == ("win-x64" if os.name == "nt" else "linux-x64")
    assert git("rev-parse", "HEAD") == args.commit and not git("status", "--porcelain"), "Clean exact source required"
    version = json.loads((ROOT / "OperatorPanel/package.json").read_text())["version"]
    assert re.fullmatch(r"[0-9]+\.[0-9]+\.[0-9]+-preview\.[0-9]+", version)
    assert ET.parse(ROOT / "ExecutionLab.Api/ExecutionLab.Api.csproj").findtext(".//Version") == version
    if os.environ.get("GITHUB_REF_TYPE") == "tag":
        assert os.environ["GITHUB_REF_NAME"] == "v" + version
    work = args.work.resolve(); work.mkdir(parents=True, exist_ok=False)
    out = args.out.resolve(); out.mkdir(parents=True, exist_ok=True)

    def run(name, command):
        with (work / (name + ".log")).open("wb") as log:
            subprocess.run(command, cwd=ROOT, stdout=log, stderr=subprocess.STDOUT, check=True, timeout=180)

    npm = shutil.which("npm.cmd" if os.name == "nt" else "npm")
    assert npm
    run("panel-build", [npm, "--prefix", "OperatorPanel", "run", "build"])
    switches = ["-p:SelfContained=false", "-p:EnableRuntimePackDownload=false", "-p:DisableTransitiveFrameworkReferenceDownloads=true"]
    restore = [args.dotnet, "restore", "ExecutionLab.Api/ExecutionLab.Api.csproj", "--runtime", args.rid, *switches]
    if args.nuget_source: restore.extend(["--source", args.nuget_source, "-p:NuGetAudit=false"])
    run("restore", restore)
    published = work / "publish"
    run("publish", [args.dotnet, "publish", "ExecutionLab.Api/ExecutionLab.Api.csproj", "-c", "Release",
                    "--runtime", args.rid, "--no-self-contained", "--no-restore", *switches,
                    "-p:DebugType=None", "-p:DebugSymbols=false", "-p:SourceRevisionId=" + args.commit,
                    "-o", str(published)])
    assert git("rev-parse", "HEAD") == args.commit and not git("status", "--porcelain"), "Source changed during build"
    name = f"trading-execution-lab-v{version}-{args.rid}"
    package = work / name
    shutil.copytree(published, package)
    assert args.commit.encode("ascii") in (package / "ExecutionLab.Api.dll").read_bytes(), "Assembly source revision is missing"
    shutil.copy2(ROOT / "scripts/Start-OperatorPanel.ps1", package / "Start-OperatorPanel.ps1")
    shutil.copy2(ROOT / "docs/QUICKSTART.md", package / "README.md")
    shutil.copy2(ROOT / "LICENSE", package / "LICENSE")
    licenses = package / "licenses"; licenses.mkdir()
    for license_path in (ROOT / "docs/licenses").iterdir():
        if license_path.is_file(): shutil.copy2(license_path, licenses / license_path.name)
    for project in ["react", "react-dom"]:
        shutil.copy2(ROOT / f"OperatorPanel/node_modules/{project}/LICENSE", licenses / (project + "-MIT.txt"))
    deps = json.loads((package / "ExecutionLab.Api.deps.json").read_text())
    assert "ExecutionLab.Api/" + version in deps["libraries"]
    assets = json.loads((ROOT / "ExecutionLab.Api/obj/project.assets.json").read_text())
    package_folders = [Path(folder) for folder in assets["packageFolders"]]
    dependencies = []
    for identity, entry in sorted(deps["libraries"].items()):
        if entry["type"] != "package": continue
        package_id, package_version = identity.split("/")
        directory = next(folder / package_id.lower() / package_version for folder in package_folders
                         if (folder / package_id.lower() / package_version).is_dir())
        # Existing packages use more than one NuSpec schema namespace.
        nuspec = ET.parse(next(directory.glob("*.nuspec"))).find("{*}metadata")
        assert nuspec is not None, identity
        license_id = nuspec.findtext("{*}license")
        assert license_id in {"MIT", "Apache-2.0"}, (identity, "Review this dependency's license before redistribution")
        dependencies.append({"package": package_id, "version": package_version, "license": license_id,
                             "copyright": nuspec.findtext("{*}copyright", default="")})
        for notice in directory.iterdir():
            if notice.is_file() and (notice.name.upper().startswith("LICENSE") or notice.name.upper().startswith("THIRD-PARTY-NOTICES")):
                shutil.copy2(notice, licenses / (package_id + "-" + notice.name))
    (package / "THIRD-PARTY-DEPENDENCIES.json").write_text(json.dumps({"nuget": dependencies,
        "browser": [{"package": x, "version": json.loads((ROOT / f"OperatorPanel/node_modules/{x}/package.json").read_text())["version"], "license": "MIT"} for x in ["react", "react-dom"]],
        "nativeSqlite": "SQLite is public domain; SQLitePCLRaw wrappers are Apache-2.0, Copyright 2014-2024 SourceGear, LLC.",
        "externalRuntime": "Not bundled. Installed ASP.NET Core .NET10 runtime and PowerShell retain their own licenses."}, indent=2) + "\n", encoding="utf-8")
    inventory = []
    for path in sorted(package.rglob("*")):
        assert not path.is_symlink()
        if not path.is_file(): continue
        relative = path.relative_to(package).as_posix()
        assert not relative.lower().endswith((".pdb", ".sqlite")) and "testhost" not in relative.lower()
        assert b"EXECUTION_LAB_OPERATOR_CODE=" not in path.read_bytes()
        inventory.append({"path": relative, "bytes": path.stat().st_size, "sha256": sha(path)})
    config = json.loads((package / "ExecutionLab.Api.runtimeconfig.json").read_text())["runtimeOptions"]
    assert "frameworks" in config and "includedFrameworks" not in config
    manifest = {"formatVersion": 1, "version": version, "rid": args.rid, "sourceCommit": args.commit,
                "sourceTree": git("rev-parse", "HEAD^{tree}"), "selfContained": False,
                "entrypoint": "dotnet ExecutionLab.Api.dll", "sdk": subprocess.check_output([args.dotnet, "--version"], text=True).strip(),
                "tools": {"node": subprocess.check_output([shutil.which("node"), "--version"], text=True).strip(),
                          "python": platform.python_version(), "powershell": subprocess.check_output(["pwsh", "--version"], text=True).strip()},
                "buildHost": {"os": platform.system(), "architecture": platform.machine()},
                "runtimeConfig": config, "files": inventory}
    (package / "BUILD-MANIFEST.json").write_text(json.dumps(manifest, indent=2) + "\n", encoding="utf-8")
    archive = out / (name + (".zip" if os.name == "nt" else ".tar.gz"))
    assert not archive.exists()
    if os.name == "nt":
        with zipfile.ZipFile(archive, "x", zipfile.ZIP_DEFLATED) as zip_file:
            for path in sorted(package.rglob("*")):
                if path.is_file(): zip_file.write(path, path.relative_to(work).as_posix())
    else:
        with tarfile.open(archive, "x:gz") as tar: tar.add(package, arcname=name)
    result = {"archive": str(archive), "sha256": sha(archive), "bytes": archive.stat().st_size,
              "sourceCommit": args.commit, "rid": args.rid, "payloadFiles": len(inventory)}
    (work / "archive.json").write_text(json.dumps(result, indent=2) + "\n", encoding="utf-8")
    print(json.dumps(result))


if __name__ == "__main__":
    main()
