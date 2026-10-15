#!/usr/bin/env python3
"""Verify the actual public locreturn release, independently of its checkout.

This script intentionally has no fallback to local dist/ or editable source.
It requires publication coordinates supplied after the release exists.
"""

from __future__ import annotations

import argparse
import base64
import csv
import hashlib
import io
import json
import os
from pathlib import Path
import platform
import re
import shutil
import subprocess
import sys
import tarfile
import tempfile
import time
import urllib.request
import zipfile


REPO = "waxwingfactor/locreturn"
BASE = "https://api.github.com/repos/" + REPO
EXPECTED_TESTS = 49
RECORDS = []
ROOT = None


def check(condition, message):
    if not condition:
        raise AssertionError(message)


def sha(data):
    return hashlib.sha256(data).hexdigest()


def public_get(url):
    request = urllib.request.Request(url, headers={
        "User-Agent": "locreturn-independent-public-release-verifier/1.0",
        "Accept": "application/vnd.github+json" if url.startswith(BASE) else "*/*",
    })
    with urllib.request.urlopen(request, timeout=90) as response:
        check(response.status == 200, "Public HTTP download failed")
        body = response.read()
        return body, response.geturl()


def api(path):
    return json.loads(public_get(BASE + path)[0])


def clean_env():
    env = dict(os.environ)
    for name in ("PYTHONPATH", "PYTHONHOME", "VIRTUAL_ENV", "__PYVENV_LAUNCHER__"):
        env.pop(name, None)
    env["PYTHONNOUSERSITE"] = "1"
    env["PIP_DISABLE_PIP_VERSION_CHECK"] = "1"
    env["PIP_NO_INPUT"] = "1"
    env["PIP_CONFIG_FILE"] = os.devnull
    return env


def redact(value):
    value = str(value)
    if ROOT:
        value = value.replace(str(ROOT), "<verification-root>")
    value = value.replace(str(Path.home()), "<user-home>")
    return value


def run(command, cwd, label, expected=0):
    result = subprocess.run(list(map(str, command)), cwd=cwd, env=clean_env(),
                            text=True, capture_output=True, timeout=240)
    record = {"label": label, "command": [redact(p) for p in command],
              "exit_code": result.returncode,
              "stdout": redact(result.stdout[-16000:]),
              "stderr": redact(result.stderr[-16000:])}
    RECORDS.append(record)
    check(result.returncode == expected,
          f"{label}: expected exit {expected}, got {result.returncode}: {record['stderr']}")
    return result


def extract_tar(data, destination):
    destination.mkdir()
    with tarfile.open(fileobj=io.BytesIO(data), mode="r:gz") as archive:
        for member in archive.getmembers():
            path = Path(member.name)
            check(not path.is_absolute() and ".." not in path.parts,
                  "Unsafe path in published archive")
            check(member.isfile() or member.isdir(),
                  "Published archive contains unsupported special/link member")
        archive.extractall(destination, filter="data")
    roots = list(destination.iterdir())
    check(len(roots) == 1 and roots[0].is_dir(), "Expected one archive root")
    return roots[0]


def catalog_flow(python, work):
    """A separately constructed workflow, relocated after review, offline."""
    before = work / "before-move"
    before.mkdir()

    def write(folder, name, value):
        (folder / name).write_text(json.dumps(value, ensure_ascii=False), encoding="utf-8")

    def read(folder, name):
        return json.loads((folder / name).read_text(encoding="utf-8"))

    source = {"greet": "Hello", "new": "New", "meaning": "Old meaning", "gone": "Gone"}
    target = {"greet": "Bonjour", "meaning": "Vieux", "gone": "Parti", "orphan": "Retain"}
    context = {"meaning": "Old context"}
    write(before, "en.json", source)
    write(before, "fr.json", target)
    write(before, "context.json", context)
    command = [python, "-I", "-m", "locreturn"]
    run(command + ["pack", "--source", "en.json", "--target", "fr.json", "--context", "context.json",
                   "--source-locale", "en", "--target-locale", "fr", "--out", "job"], before, "offline-pack")
    task = read(before, "job/task.json")
    for key, value in {"greet": "Salut", "new": "Nouveau", "meaning": "Retour ancien", "gone": "Disparu"}.items():
        task["entries"][key]["translation"] = value
    write(before, "job/task.json", task)
    target["greet"] = "Local review"
    source["meaning"] = "New meaning"
    del source["gone"]
    context["meaning"] = "New context"
    write(before, "en.json", source)
    write(before, "fr.json", target)
    write(before, "context.json", context)
    common = ["--source", "en.json", "--target", "fr.json", "--context", "context.json",
              "--baseline", "job/baseline.json", "--returned", "job/task.json"]
    run(command + ["plan", *common, "--out", "review"], before, "offline-plan-conflicts", 3)
    plan = read(before, "review/plan.json")
    states = {row["key"]: row["status"] for row in plan["rows"]}
    check(states["greet"] == "target-conflict" and states["meaning"] == "source-changed"
          and states["gone"] == "source-removed" and states["new"] == "ready",
          "Independent expected classifications failed")
    run(command + ["apply", *common, "--plan", "review/plan.json", "--out", "unresolved"],
        before, "offline-unresolved-refusal", 2)
    check(not (before / "unresolved").exists(), "Unresolved apply wrote output")
    decisions = read(before, "review/decisions.json")
    decisions["entries"] = {
        "greet": {"action": "keep", "text": None, "reason": "Independent reviewer keeps local correction"},
        "meaning": {"action": "custom", "text": "Sens revu", "reason": "Independent review of current meaning and context"},
        "gone": {"action": "keep", "text": None, "reason": "Retain orphan under explicit no-pruning policy"},
    }
    write(before, "review/decisions.json", decisions)
    # Show a source-qualified gate cannot be bypassed with incoming action.
    bad = json.loads(json.dumps(decisions))
    bad["entries"]["meaning"]["action"] = "incoming"
    bad["entries"]["meaning"]["text"] = None
    write(before, "bad-decisions.json", bad)
    run(command + ["apply", *common, "--plan", "review/plan.json", "--decisions", "bad-decisions.json",
                   "--out", "source-bypass"], before, "offline-source-gate-refusal", 2)
    check(not (before / "source-bypass").exists(), "Source bypass wrote output")
    relocated = work / "after-move"
    before.rename(relocated)
    run(command + ["apply", *common, "--plan", "review/plan.json", "--decisions", "review/decisions.json",
                   "--out", "merged"], relocated, "relocated-offline-apply")
    result = read(relocated, "merged/target.json")
    expected = dict(target, new="Nouveau", meaning="Sens revu")
    check(result == expected, "Unexpected relocated merged catalog")
    check(read(relocated, "fr.json") == target, "Input target mutated")
    receipt = read(relocated, "merged/receipt.json")
    canonical_result = json.dumps(result, ensure_ascii=False, sort_keys=True,
                                  separators=(",", ":"), allow_nan=False).encode()
    check(receipt["output_sha256"] == sha(canonical_result), "Receipt output hash mismatch")
    source["new"] = "An unrelated later edit"
    write(relocated, "en.json", source)
    run(command + ["apply", *common, "--plan", "review/plan.json", "--decisions", "review/decisions.json",
                   "--out", "stale"], relocated, "offline-stale-plan-refusal", 2)
    check(not (relocated / "stale").exists(), "Stale apply wrote output")
    return {"classifications": states, "output": result,
            "receipt_output_sha256": receipt["output_sha256"],
            "relocated": True, "inputs_unchanged": True, "network_blocked": True,
            "unresolved_refused": True, "source_gate_refused": True, "stale_refused": True}


def main():
    global ROOT
    parser = argparse.ArgumentParser()
    parser.add_argument("--release-url", required=True)
    parser.add_argument("--source-commit", required=True)
    parser.add_argument("--ci-run-id", required=True, type=int)
    parser.add_argument("--out", type=Path, required=True)
    args = parser.parse_args()
    check(args.release_url == "https://github.com/waxwingfactor/locreturn/releases/tag/v1.0.0",
          "This verifier targets the actual public locreturn v1.0.0 release")
    check(re.fullmatch(r"[0-9a-f]{40}", args.source_commit), "Full expected source SHA required")
    ROOT = args.out.resolve()
    ROOT.mkdir()
    downloads = ROOT / "downloads"
    downloads.mkdir()
    evidence = {"schema": "locreturn.independent-public-verification.v1",
                "started_utc": time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime()),
                "release_url": args.release_url, "repository": REPO,
                "expected_source_commit": args.source_commit,
                "environment": {"python": platform.python_version(), "platform": platform.platform()},
                "isolation": {"outside_checkout": True, "PYTHONPATH_removed": True,
                              "user_site_disabled": True, "isolated_python_mode": True},
                "commands": RECORDS, "status": "running"}
    try:
        release = api("/releases/tags/v1.0.0")
        check(not release["draft"] and not release["prerelease"], "Release is not public stable")
        commit = api("/commits/v1.0.0")
        check(commit["sha"] == args.source_commit, "Public source tag does not match expected revision")
        ci = api(f"/actions/runs/{args.ci_run_id}")
        check(ci["head_sha"] == args.source_commit and ci["status"] == "completed"
              and ci["conclusion"] == "success", "Public CI run does not verify source revision")
        jobs = api(f"/actions/runs/{args.ci_run_id}/jobs?per_page=100")["jobs"]
        check(jobs and all(job["conclusion"] == "success" for job in jobs)
              and any(job["name"] == "quality-gate" for job in jobs), "Public required CI jobs did not pass")
        evidence["public_release"] = {"id": release["id"], "published_at": release["published_at"],
                                      "tag_name": release["tag_name"], "source_commit": commit["sha"]}
        evidence["public_ci"] = {"run_url": ci["html_url"], "head_sha": ci["head_sha"],
                                 "conclusion": ci["conclusion"],
                                 "jobs": [{"name": j["name"], "conclusion": j["conclusion"]} for j in jobs]}
        by_name = {asset["name"]: asset for asset in release["assets"]}
        names = ["locreturn-1.0.0-py3-none-any.whl", "locreturn-1.0.0.tar.gz", "SHA256SUMS", "PROVENANCE.json"]
        for name in names:
            check(name in by_name, f"Actual public release asset missing: {name}")
        downloaded = {}
        evidence["downloads"] = []
        for name in names:
            data, final_url = public_get(by_name[name]["browser_download_url"])
            (downloads / name).write_bytes(data)
            downloaded[name] = data
            evidence["downloads"].append({"name": name, "url": by_name[name]["browser_download_url"],
                                           "size": len(data), "sha256": sha(data),
                                           "public_unauthenticated_http": 200})
        sums = {}
        for line in downloaded["SHA256SUMS"].decode().splitlines():
            expected_hash, name = line.split(None, 1)
            sums[name.lstrip("*")] = expected_hash
        provenance = json.loads(downloaded["PROVENANCE.json"])
        check(provenance["repository"] == REPO and provenance["source_commit"] == args.source_commit,
              "Published provenance repository/revision mismatch")
        check(provenance["run_url"] == ci["html_url"], "Published provenance CI mismatch")
        for name in names[:2]:
            check(sha(downloaded[name]) == sums[name] == provenance["artifacts"][name],
                  f"Published checksums/provenance disagree: {name}")
        evidence["provenance"] = provenance
        source_data, _ = public_get(BASE + "/tarball/v1.0.0")
        (downloads / "source-tag-v1.0.0.tar.gz").write_bytes(source_data)
        source_root = extract_tar(source_data, ROOT / "source-tag")
        sdist_root = extract_tar(downloaded[names[1]], ROOT / "published-sdist")
        comparisons = []
        for relative in [p.relative_to(source_root) for directory in ("src/locreturn", "tests", "examples", "docs")
                         for p in (source_root / directory).rglob("*") if p.is_file()]:
            source_file, sdist_file = source_root / relative, sdist_root / relative
            check(sdist_file.is_file(), f"Published sdist missing source-tag file: {relative}")
            check(source_file.read_bytes() == sdist_file.read_bytes(), f"Published sdist differs from tag: {relative}")
            comparisons.append({"path": str(relative), "sha256": sha(source_file.read_bytes())})
        wheel_code = []
        with zipfile.ZipFile(io.BytesIO(downloaded[names[0]])) as wheel:
            records = [name for name in wheel.namelist() if name.endswith(".dist-info/RECORD")]
            check(len(records) == 1, "Wheel RECORD missing")
            for name, digest, size in csv.reader(io.StringIO(wheel.read(records[0]).decode())):
                if not digest:
                    continue
                check(digest.startswith("sha256="), "Unsupported wheel hash algorithm")
                data = wheel.read(name)
                encoded_hash = base64.urlsafe_b64encode(hashlib.sha256(data).digest()).rstrip(b"=").decode()
                check(digest == "sha256=" + encoded_hash and len(data) == int(size), "Wheel RECORD mismatch")
            for name in wheel.namelist():
                if name.startswith("locreturn/") and name.endswith(".py"):
                    data = wheel.read(name)
                    check(data == (source_root / "src" / name).read_bytes(), f"Wheel source mismatch: {name}")
                    wheel_code.append({"path": name, "sha256": sha(data)})
        check(len(wheel_code) == 5, "Expected five supported wheel Python source files")
        evidence["source_comparison"] = {"tag_archive_sha256": sha(source_data),
                                         "published_sdist_files_equal_tag": comparisons,
                                         "wheel_code_equal_tag": wheel_code, "wheel_RECORD_valid": True}
        # Fetch build tooling separately, then both artifact installations run without an index.
        tools_dir = ROOT / "build-dependencies"
        tools_dir.mkdir()
        run([sys.executable, "-m", "pip", "download", "--only-binary=:all:", "--dest", tools_dir,
             "setuptools>=77", "wheel"], ROOT, "download-sdist-build-tooling")
        evidence["build_dependencies"] = [{"name": p.name, "sha256": sha(p.read_bytes())}
                                           for p in sorted(tools_dir.iterdir())]
        evidence["installations"] = []
        for kind, name in (("wheel", names[0]), ("sdist", names[1])):
            install_root = ROOT / (kind + "-verification")
            install_root.mkdir()
            venv = install_root / "venv"
            run([sys.executable, "-m", "venv", venv], ROOT, kind + "-create-fresh-venv")
            python = venv / "bin/python"
            run([python, "-m", "pip", "install", "--no-index", "--find-links", tools_dir,
                 downloads / name], install_root, kind + "-install-published-artifact")
            imported = run([python, "-I", "-c",
                            "import json,locreturn,sys; print(json.dumps({'file':locreturn.__file__,'prefix':sys.prefix,'version':locreturn.__version__}))"],
                           install_root, kind + "-installed-import-origin")
            location = json.loads(imported.stdout)
            check(Path(location["file"]).resolve().is_relative_to(venv), "Imported checkout or user-site code")
            check(location["version"] == "1.0.0", "Installed version mismatch")
            installed_py = Path(location["file"]).parent
            for file in installed_py.glob("*.py"):
                check(file.read_bytes() == (source_root / "src/locreturn" / file.name).read_bytes(),
                      "Installed source differs from verified release/tag")
            # This sitecustomize is a verifier fixture inside its fresh venv.
            # It blocks all socket audit events in both parent test and CLI subprocesses.
            (installed_py.parent / "sitecustomize.py").write_text(
                "import sys\ndef _block(event,args):\n"
                "    if event.startswith('socket.'):\n"
                "        raise RuntimeError('Network disabled for independent release verification')\n"
                "sys.addaudithook(_block)\n", encoding="utf-8")
            run([python, "-I", "-c",
                 "import socket\ntry:\n socket.create_connection(('example.com',443))\nexcept RuntimeError as e:\n print(e)\nelse:\n raise AssertionError('socket block inactive')"],
                install_root, kind + "-confirm-network-block")
            tests = run([python, "-I", "-m", "unittest", "discover", "-s", sdist_root / "tests", "-v"],
                        install_root, kind + "-all-published-sdist-tests-offline")
            match = re.search(r"Ran (\d+) tests?", tests.stderr)
            check(match and int(match.group(1)) == EXPECTED_TESTS, "Unexpected published test count")
            run([python, "-I", sdist_root / "examples/demo.py"], install_root, kind + "-published-example-offline")
            run([venv / "bin/locreturn", "--version"], install_root, kind + "-console-script")
            flow = catalog_flow(python, install_root)
            evidence["installations"].append({"artifact": name, "kind": kind,
                                                "version": location["version"],
                                                "import_origin": redact(location["file"]),
                                                "test_count": int(match.group(1)), "tests_passed": True,
                                                "example_passed": True, "independent_flow": flow})
        evidence["status"] = "passed"
        evidence["completed_utc"] = time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime())
    except BaseException as exc:
        evidence["status"] = "failed"
        evidence["error"] = redact(f"{type(exc).__name__}: {exc}")
        raise
    finally:
        (ROOT / "evidence.json").write_text(json.dumps(evidence, indent=2, ensure_ascii=True) + "\n")
    print(json.dumps({"status": evidence["status"], "test_runs": [i["test_count"] for i in evidence["installations"]],
                      "release_url": args.release_url, "source_commit": args.source_commit,
                      "evidence": redact(ROOT / "evidence.json")}))


if __name__ == "__main__":
    main()
