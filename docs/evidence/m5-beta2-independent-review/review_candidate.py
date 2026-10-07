"""Black-box local beta.2 review using the actual frozen beta.1 baseline.

Writes only to new review output and an owned /tmp workspace. No network or
host client is used. Tool commands come from the independently unpacked beta.2
candidate and remain fixed argv; no metadata-supplied command runs.
"""
from __future__ import annotations

import argparse
import hashlib
import json
from pathlib import Path
import subprocess
import sys
import tarfile
import tempfile


EXPECTED_BETA1 = "2c44459c195540fd3ac99a0fa7f52583090d85eae47b26fea4a64d1da85ff9ff"
EXPECTED_BETA2 = "763fff38af08c735ead53d95a0684904307ee6546f7e7538d9835c3187a72bf3"
REQUIRED_TOOLS = (
    "scripts/m5_host_install.py", "scripts/m5_host_smoke.py", "scripts/m5_host_uninstall.py",
    "scripts/m5_reliability_smoke.py", "tests/test_m5_host_install.py", "tests/test_m5_host_smoke.py",
    "tests/test_m5_host_uninstall.py", "tests/test_m5_reliability_smoke.py",
)
HOST_TARGETS = {"codex": ".agents/skills/archcanvas", "claude-code": ".claude/skills/archcanvas",
                "deepseek-harness": ".dsh/skills/archcanvas"}


def sha(path):
    return hashlib.sha256(path.read_bytes()).hexdigest()


def inventory(root):
    return {path.relative_to(root).as_posix(): {"bytes": path.stat().st_size, "sha256": sha(path)}
            for path in sorted(root.rglob("*")) if path.is_file() and not path.is_symlink()}


def require(value, message):
    if not value:
        raise ValueError(message)


def write(path, value):
    path.write_text(json.dumps(value, ensure_ascii=False, indent=2, allow_nan=False) + "\n", encoding="utf-8")


def run_review(root, output):
    root, output = root.resolve(), output.absolute()
    require(not output.exists() and not output.is_symlink(), "Review output must be a new directory.")
    output.mkdir(parents=True)
    beta1, beta2 = [root / f".archcanvas/releases/archcanvas-0.1.0-beta.{n}.tar.gz" for n in (1, 2)]
    require(sha(beta1) == EXPECTED_BETA1, "Frozen beta.1 digest differs.")
    require(sha(beta2) == EXPECTED_BETA2, "Candidate beta.2 digest differs.")
    work = Path(tempfile.mkdtemp(prefix="archcanvas-beta2-independent-review-"))
    result = {"schema": "archcanvas-m5-beta2-independent-review/1", "status": "running",
              "scope": "actual-frozen-beta1-beta2-packaged-lifecycle", "candidate": str(beta2),
              "candidateSha256": EXPECTED_BETA2, "baseline": str(beta1), "baselineSha256": EXPECTED_BETA1,
              "temporaryRoot": str(work), "hostE2E": "not-tested", "modelExecution": False,
              "humanApproval": False, "sourceCommitted": False, "commands": [], "checks": [], "hosts": [],
              "limitations": ["Three host filesystem layouts are exercised; real host clients and host E2E remain not-tested.",
                              "No model is imported or executed. These commands only analyze source and change owned local installation pointers/directories.",
                              "No browser gestures, publication review, dependencies installation, public release or cross-platform lifecycle certification."]}

    def command(tool, arguments, label):
        argv = [sys.executable, "-B", str(tool), *arguments]
        proc = subprocess.run(argv, cwd=work, capture_output=True, text=True, timeout=120)
        (output / (label + ".stdout.txt")).write_text(proc.stdout, encoding="utf-8")
        (output / (label + ".stderr.txt")).write_text(proc.stderr, encoding="utf-8")
        require(proc.returncode == 0, f"{label} failed ({proc.returncode}): {proc.stdout} {proc.stderr}")
        value = json.loads(proc.stdout)
        require(value.get("status") == "passed", f"{label} did not report passed.")
        write(output / (label + ".json"), value)
        result["commands"].append({"label": label, "argv": argv, "exitCode": proc.returncode,
                                   "stdoutSha256": sha(output / (label + ".stdout.txt")),
                                   "stderrSha256": sha(output / (label + ".stderr.txt")), "result": label + ".json"})
        return value

    try:
        # Bootstrap verify uses the current formal verifier. All remaining
        # lifecycle commands run from the frozen candidate's scripts tree.
        release2, release1 = work / "beta2-release", work / "beta1-release"
        initial = command(root / "scripts/m5_beta_bundle.py", ["verify", "--bundle", str(beta2), "--extract-to", str(release2)], "candidate-verify")
        require(initial["version"] == "0.1.0-beta.2" and initial["fileCount"] == 258, "Candidate version/file count differs.")
        require(initial["analysis"]["modelExecution"] is False, "Candidate claims model execution.")
        require([item["nodeCount"] for item in initial["analysis"]["fixtures"]] == [8, 24, 49], "Static fixture facts differ.")
        require(all(Path(path).is_relative_to(release2 / "src") for path in initial["analysis"]["origins"]), "Candidate analysis resolved another runtime.")
        tool, installer, lifecycle = [release2 / "scripts" / name for name in ("m5_beta_bundle.py", "m5_host_install.py", "m5_host_uninstall.py")]
        require(all((release2 / path).is_file() for path in REQUIRED_TOOLS), "Candidate lifecycle utility missing.")
        package_manifest = json.loads((release2 / "BUNDLE-MANIFEST.json").read_text())
        require({row["path"] for row in package_manifest["files"]} >= set(REQUIRED_TOOLS), "Candidate tools not inventoried.")
        mismatch = [row["path"] for row in package_manifest["files"]
                    if not (root / row["path"]).is_file() or sha(root / row["path"]) != row["sha256"]]
        result["candidateCurrentWorktreeByteMismatches"] = mismatch
        result["candidateInventory"] = package_manifest
        result["checks"].append({"check": "candidate-258-files-tools-and-three-static-fixtures", "status": "passed"})

        command(tool, ["verify", "--bundle", str(beta1), "--extract-to", str(release1)], "packaged-tool-verifies-frozen-beta1")
        prefix = work / "version-prefix"
        first = command(tool, ["install", "--bundle", str(beta1), "--prefix", str(prefix), "--activate"], "prefix-beta1-install")
        baseline_bytes = inventory(Path(first["installedDirectory"]))
        prefix_user = prefix / "user-data.json"
        prefix_user.write_bytes(b"User data remains outside releases.\n")
        second = command(tool, ["install", "--bundle", str(beta2), "--prefix", str(prefix), "--activate"], "prefix-beta2-upgrade")
        candidate_bytes = inventory(Path(second["installedDirectory"]))
        require(second["activation"]["previousVersion"] == "0.1.0-beta.1", "Upgrade lost previous version.")
        require((prefix / "current").resolve() == Path(second["installedDirectory"]), "Upgrade current pointer differs.")
        require(inventory(Path(first["installedDirectory"])) == baseline_bytes, "Upgrade changed frozen beta.1 installation.")
        rollback = command(tool, ["rollback", "--prefix", str(prefix), "--version", "0.1.0-beta.1"], "prefix-beta1-rollback")
        require(rollback["previousVersion"] == "0.1.0-beta.2", "Rollback lost previous beta.2 version.")
        require((prefix / "current").resolve() == Path(first["installedDirectory"]), "Rollback current pointer differs.")
        require(inventory(Path(first["installedDirectory"])) == baseline_bytes, "Rollback changed beta.1 bytes.")
        require(inventory(Path(second["installedDirectory"])) == candidate_bytes, "Rollback changed beta.2 bytes.")
        require(prefix_user.read_bytes() == b"User data remains outside releases.\n", "Version switch changed user data.")
        write(output / "prefix-beta1-inventory.json", baseline_bytes)
        write(output / "prefix-beta2-inventory.json", candidate_bytes)
        result["checks"].append({"check": "actual-beta1-beta2-beta1-install-upgrade-rollback", "status": "passed",
                                   "beta1Files": len(baseline_bytes), "beta2Files": len(candidate_bytes), "userDataUnchanged": True})

        for host, relative in HOST_TARGETS.items():
            workspace = work / ("workspace-" + host)
            workspace.mkdir()
            state = workspace / "external-state"
            state.mkdir()
            (state / "document.json").write_bytes(b"Existing document survives host lifecycle.\n")
            external_before = inventory(state)
            skill = workspace / relative
            command(installer, ["install", "--release-dir", str(release1), "--host", host, "--workspace", str(workspace)], host + "-install-beta1")
            old_bytes = inventory(skill)
            preview1 = command(lifecycle, ["preview", "--host", host, "--workspace", str(workspace)], host + "-preview-beta1")
            require(preview1["writesPerformed"] is False and inventory(skill) == old_bytes, "Preview changed old installation.")
            archived1 = command(lifecycle, ["uninstall", "--host", host, "--workspace", str(workspace), "--expected-installation-sha256", preview1["installationSha256"]], host + "-archive-beta1")
            archive1 = Path(archived1["archiveDirectory"])
            require(not skill.exists() and inventory(archive1 / "skill") == old_bytes, "Old archive lost bytes or discovery path stayed present.")
            installed2 = command(installer, ["install", "--release-dir", str(release2), "--host", host, "--workspace", str(workspace)], host + "-install-beta2")
            require(installed2["version"] == "0.1.0-beta.2", "Host upgrade installed wrong version.")
            new_bytes = inventory(skill)
            require(old_bytes != new_bytes, "Different host versions have same complete inventory.")
            preview2 = command(lifecycle, ["preview", "--host", host, "--workspace", str(workspace)], host + "-preview-beta2")
            archived2 = command(lifecycle, ["uninstall", "--host", host, "--workspace", str(workspace), "--expected-installation-sha256", preview2["installationSha256"]], host + "-archive-beta2")
            archive2 = Path(archived2["archiveDirectory"])
            require(archive1 != archive2 and inventory(archive2 / "skill") == new_bytes, "New archive lost bytes.")
            restored = command(lifecycle, ["restore", "--host", host, "--workspace", str(workspace), "--archive-directory", str(archive1)], host + "-restore-beta1")
            verified = command(installer, ["verify", "--skill-directory", str(skill)], host + "-verify-restored-beta1")
            require(restored["version"] == verified["version"] == "0.1.0-beta.1", "Host restore did not return to beta.1.")
            require(inventory(skill) == old_bytes and inventory(archive2 / "skill") == new_bytes, "Restore changed old/new installation bytes.")
            require(inventory(state) == external_before, "Host lifecycle changed external user state.")
            require(not (archive1 / "skill").exists() and json.loads((archive1 / "archive.json").read_text())["status"] == "restored", "Consumed archive not recorded.")
            require(restored["hostE2E"] == verified["hostE2E"] == "not-tested", "Host client E2E claim was upgraded.")
            write(output / (host + "-beta1-inventory.json"), old_bytes)
            write(output / (host + "-beta2-inventory.json"), new_bytes)
            result["hosts"].append({"host": host, "status": "passed", "discoveryPath": relative,
                                    "beta1Files": len(old_bytes), "beta2Files": len(new_bytes),
                                    "versionSequence": ["0.1.0-beta.1", "archived", "0.1.0-beta.2", "archived", "0.1.0-beta.1"],
                                    "oldNewBytesPreserved": True, "externalDataUnchanged": True, "hostE2E": "not-tested"})
        require(sha(beta1) == EXPECTED_BETA1 and sha(beta2) == EXPECTED_BETA2, "Input archive changed during review.")
        result["checks"].append({"check": "both-frozen-input-archives-unchanged", "status": "passed"})
        result["status"] = "passed"
    except Exception as exc:
        result["status"], result["error"] = "failed", str(exc)
    finally:
        result["reviewScriptSha256"] = sha(Path(__file__))
        result["artifacts"] = [{"path": str(path.relative_to(output)), "bytes": path.stat().st_size, "sha256": sha(path)}
                               for path in sorted(output.rglob("*")) if path.is_file() and path.name != "report.json"]
        write(output / "report.json", result)
    return result


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--project-root", type=Path, required=True)
    parser.add_argument("--output", type=Path, required=True)
    options = parser.parse_args()
    result = run_review(options.project_root, options.output)
    print(json.dumps({key: result.get(key) for key in ("status", "error", "temporaryRoot", "checks", "hosts")}, ensure_ascii=False, indent=2))
    raise SystemExit(0 if result["status"] == "passed" else 1)
