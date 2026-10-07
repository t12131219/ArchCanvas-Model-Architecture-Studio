"""Run retained CLI lifecycle evidence against frozen beta.1, without models."""
import hashlib
import json
from pathlib import Path
import subprocess
import sys
import tempfile
from datetime import datetime, timezone

ROOT = Path(__file__).resolve().parents[3]
OUT = Path(__file__).resolve().parent
sys.path.insert(0, str(ROOT))
from scripts.m5_host_install import HOST_TARGETS


def sha(raw):
    return hashlib.sha256(raw).hexdigest()


def inventory(root):
    return {str(p.relative_to(root)): {"bytes": p.stat().st_size, "sha256": sha(p.read_bytes())}
            for p in sorted(root.rglob("*")) if p.is_file()}


def run(name, command):
    started = datetime.now(timezone.utc).isoformat()
    proc = subprocess.run(command, cwd=ROOT, capture_output=True, text=True, timeout=90)
    record = {"command": [str(arg) for arg in command], "startedAt": started,
              "exitCode": proc.returncode, "stdout": proc.stdout, "stderr": proc.stderr}
    path = OUT / (name + ".process.json")
    if path.exists():
        raise RuntimeError("refusing to overwrite process evidence: " + str(path))
    path.write_text(json.dumps(record, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    if proc.returncode:
        raise RuntimeError(f"{name} failed: {proc.stderr or proc.stdout}")
    return json.loads(proc.stdout)


work = Path(tempfile.mkdtemp(prefix="archcanvas-uninstall-cli-"))
bundle = ROOT / ".archcanvas/releases/archcanvas-0.1.0-beta.1.tar.gz"
bundle_before = sha(bundle.read_bytes())
release = work / "release"
run("00-verify-beta1", [sys.executable, ROOT / "scripts/m5_beta_bundle.py", "verify", "--bundle", bundle, "--extract-to", release])
results = []
for host, relative in HOST_TARGETS.items():
    workspace = work / host
    workspace.mkdir()
    external = workspace / "external-data"
    external.mkdir()
    (external / "canvas.json").write_bytes(b'{"user":"preserve"}\n')
    external_before = inventory(external)
    skill = workspace / relative
    run(host + "-01-install", [sys.executable, ROOT / "scripts/m5_host_install.py", "install", "--release-dir", release, "--host", host, "--workspace", workspace])
    before = inventory(skill)
    pre = run(host + "-02-preview", [sys.executable, ROOT / "scripts/m5_host_uninstall.py", "preview", "--host", host, "--workspace", workspace])
    un = run(host + "-03-uninstall", [sys.executable, ROOT / "scripts/m5_host_uninstall.py", "uninstall", "--host", host, "--workspace", workspace, "--expected-installation-sha256", pre["installationSha256"]])
    archive = Path(un["archiveDirectory"])
    absent = not (skill.exists() or skill.is_symlink())
    archive_equal = inventory(archive / "skill") == before
    restored = run(host + "-04-restore", [sys.executable, ROOT / "scripts/m5_host_uninstall.py", "restore", "--host", host, "--workspace", workspace, "--archive-directory", archive])
    run(host + "-05-verify-restored", [sys.executable, ROOT / "scripts/m5_host_install.py", "verify", "--skill-directory", skill])
    final_equal = inventory(skill) == before
    external_equal = inventory(external) == external_before
    if not all((absent, archive_equal, final_equal, external_equal)):
        raise RuntimeError("lifecycle byte preservation failed: " + host)
    results.append({"host": host, "workspace": str(workspace), "skill": str(skill),
                    "archive": str(archive), "fileCount": len(before),
                    "discoveryAbsentAfterUninstall": absent, "archivedExact": archive_equal,
                    "restoredExact": final_equal, "externalDataExact": external_equal,
                    "installationSha256": pre["installationSha256"],
                    "hostE2E": "not-tested"})
bundle_after = sha(bundle.read_bytes())
if bundle_before != bundle_after:
    raise RuntimeError("frozen beta.1 changed")
bindings = []
for name in ("scripts/m5_host_uninstall.py", "tests/test_m5_host_uninstall.py", "docs/m5-host-install.md"):
    path = ROOT / name
    bindings.append({"path": name, "bytes": path.stat().st_size, "sha256": sha(path.read_bytes())})
for path in sorted(OUT.glob("*.process.json")):
    bindings.append({"path": str(path.relative_to(ROOT)), "bytes": path.stat().st_size, "sha256": sha(path.read_bytes())})
receipt = {"schema": "archcanvas-m5-host-uninstall-evidence/1", "status": "passed",
           "createdAt": datetime.now(timezone.utc).isoformat(), "runtime": sys.executable,
           "retainedWorkDirectory": str(work), "frozenBeta1Sha256": bundle_before,
           "frozenBeta1Unchanged": bundle_before == bundle_after, "hostLifecycles": results,
           "testSuite": {"passed": 12, "total": 12, "input": "temporary pack(ROOT) candidate; beta.1 not required by tests",
                         "log": "docs/evidence/m5-host-uninstall-v1/tests-candidate.txt"},
           "boundaries": {"modelExecuted": False, "globalInstallChanged": False, "externalDataChanged": False,
                          "filesDeleted": False, "differentVersionUpgradeTested": False,
                          "windowsRenameExercised": False, "macOsAtomicRenameSupported": False,
                          "hostE2E": {host: "not-tested" for host in HOST_TARGETS}},
           "bindings": bindings}
output = OUT / "receipt.json"
if output.exists():
    raise RuntimeError("refusing to overwrite final receipt")
output.write_text(json.dumps(receipt, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
print(json.dumps({"status": "passed", "hosts": len(results), "testSuite": receipt["testSuite"], "receipt": str(output)}, ensure_ascii=False, indent=2))
