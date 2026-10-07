"""Replay local package verification; keep private service state in /tmp."""
import hashlib
import json
from pathlib import Path
import shutil
import sys
import tempfile

ROOT = Path(__file__).resolve().parents[3]
sys.path.insert(0, str(ROOT / "scripts"))
from m5_beta_bundle import verify
from m5_host_install import HOST_TARGETS, install_host
from m5_host_smoke import run_smoke
from m5_reliability_smoke import run_reliability


def save(path, value):
    path.write_text(json.dumps(value, ensure_ascii=False, indent=2) + "\n")


def main():
    output = Path(__file__).resolve().parent
    work = Path(tempfile.mkdtemp(prefix="archcanvas-beta2-final-"))
    release = work / "release"
    bundle = ROOT / ".archcanvas/releases/archcanvas-0.1.0-beta.2.tar.gz"
    verified = verify(bundle, release)
    save(output / "independent-extraction.json", verified)
    results = {"schema": "archcanvas-m5-beta2-installed-verification/1", "status": "running",
               "workingDirectory": str(work), "releaseDirectory": str(release),
               "bundle": {"path": str(bundle), "sha256": hashlib.sha256(bundle.read_bytes()).hexdigest()},
               "independentExtraction": verified, "hosts": [], "modelExecution": False,
               "humanApproval": False, "hostE2E": "not-tested", "privateStateCopiedIntoEvidence": False}
    for host in HOST_TARGETS:
        workspace = work / host
        workspace.mkdir()
        installation = install_host(release, workspace, host)
        skill = workspace / HOST_TARGETS[host]
        row = {"host": host, "installation": installation}
        for name, check in (("cli-http", run_smoke), ("reliability", run_reliability)):
            temporary_output = work / f"{host}-{name}"
            receipt = check(skill, temporary_output, Path(sys.executable))
            evidence = output / f"installed-{host}-{name}"
            evidence.mkdir(exist_ok=False)
            # Only probe artifacts in its root. Never copy state/transactions,
            # session material, an approval-key, or the unrelated working dir.
            for path in temporary_output.iterdir():
                if path.is_file():
                    shutil.copyfile(path, evidence / path.name)
            row[name] = {"status": receipt["status"], "receipt": str(evidence / "receipt.json"),
                         "checkCount": len(receipt["checks"]), "privateState": str(temporary_output / "state")}
        results["hosts"].append(row)
    results["status"] = "passed" if all(row[key]["status"] == "passed" for row in results["hosts"]
                                       for key in ("cli-http", "reliability")) else "failed"
    results["inputs"] = [{"path": str(path), "sha256": hashlib.sha256(path.read_bytes()).hexdigest()}
                         for path in (Path(__file__).resolve(), ROOT / "scripts/m5_beta_bundle.py",
                                      ROOT / "scripts/m5_host_install.py", ROOT / "scripts/m5_host_smoke.py",
                                      ROOT / "scripts/m5_reliability_smoke.py")]
    save(output / "installed-verification.json", results)
    print(json.dumps({"status": results["status"], "work": str(work), "hosts": [
        {"host": row["host"], "cli-http": row["cli-http"]["status"], "reliability": row["reliability"]["status"]}
        for row in results["hosts"]]}, indent=2))
    return 0 if results["status"] == "passed" else 2


if __name__ == "__main__":
    raise SystemExit(main())
