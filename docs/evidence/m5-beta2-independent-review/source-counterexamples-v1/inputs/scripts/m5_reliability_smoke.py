#!/usr/bin/env python3
"""Check refused edits and restart recovery in an installed local Beta.

Uses an owned loopback service and a new explicit evidence/state directory.
No model execution, concrete approval, source commit, or host-client claim.
"""
from __future__ import annotations

import argparse
import copy
import json
from pathlib import Path
import sys
import time
from urllib.error import HTTPError

try:
    from .m5_host_install import verify_install
    from .m5_host_smoke import Client, LocalService, canvas, digest, require, verify_origins, write_json
except ImportError:
    from m5_host_install import verify_install
    from m5_host_smoke import Client, LocalService, canvas, digest, require, verify_origins, write_json


class FailureClient(Client):
    def response(self, path: str, method: str = "GET", body=None) -> tuple[int, dict]:
        try:
            code, raw, _ = self.request(path, method, body)
        except HTTPError as error:
            with error:
                code, raw = error.code, error.read()
        result = json.loads(raw)
        require(isinstance(result, dict), "API response must be an object.")
        return code, result

    def expect(self, path: str, method: str, body, status: int) -> dict:
        code, result = self.response(path, method, body)
        require(code == status, f"Expected HTTP {status} for {path}; got {code}.")
        return result


def draft() -> dict:
    # Handwritten graph, independent of the UI's preset/generation helpers.
    return {"schemaVersion": 1, "mode": "authored-draft", "id": "draft-fade01",
            "title": "M5 recovery probe", "revision": 1,
            "nodes": [
                {"id": "input", "kind": "Input", "label": "Input", "parameters": {"shape": [2, 16]}, "position": {"x": 0, "y": 0}},
                {"id": "linear", "kind": "Linear", "label": "Linear", "parameters": {"in_features": 16, "out_features": 8}, "position": {"x": 220, "y": 0}},
                {"id": "output", "kind": "Output", "label": "Output", "parameters": {}, "position": {"x": 440, "y": 0}}],
            "edges": [
                {"id": "e1", "source": {"nodeId": "input", "portId": "output"}, "target": {"nodeId": "linear", "portId": "input"}},
                {"id": "e2", "source": {"nodeId": "linear", "portId": "output"}, "target": {"nodeId": "output", "portId": "input"}}]}


def file_inventory(directory: Path) -> dict[str, str]:
    return {path.relative_to(directory).as_posix(): digest(path.read_bytes())
            for path in directory.rglob("*") if path.is_file()}


def exercise_refusals(client: FailureClient, state: Path, output: Path) -> dict:
    checks = []

    def unchanged(name: str, request, expected: int, assertion):
        before = file_inventory(state)
        result = client.expect(*request, expected)
        assertion(result)
        require(file_inventory(state) == before, f"Refused {name} changed persisted files.")
        write_json(output / f"{name}.json", {"httpStatus": expected, "body": result, "storageUnchanged": True})
        checks.append({"check": name, "status": "passed", "httpStatus": expected, "storageUnchanged": True})

    value = draft()
    saved = client.expect("/api/authoring/drafts/" + value["id"], "POST", {"draft": value, "expectedRevision": 0}, 200)
    require(saved == {"draft": value, "revision": 1}, "Initial draft differs.")
    bad_connection = copy.deepcopy(value)
    bad_connection["edges"][0]["source"]["portId"] = "input"
    unchanged("wrong-port-direction", ("/api/authoring/validate", "POST", {"draft": bad_connection}), 400,
              lambda result: require(any(d.get("code") == "invalid_connection_endpoint" and d.get("edgeId") == "e1"
                                         for d in result.get("diagnostics", [])), "Wrong connection did not identify e1."))
    bad_shape = copy.deepcopy(value)
    bad_shape["nodes"][1]["parameters"]["in_features"] = 12
    unchanged("shape-conflict-save", ("/api/authoring/drafts/" + value["id"], "POST", {"draft": bad_shape, "expectedRevision": 1}), 400,
              lambda result: require(any(d.get("code") == "linear_input_features_mismatch" and d.get("nodeId") == "linear"
                                         for d in result.get("diagnostics", [])), "Shape failure did not identify Linear."))
    modified = copy.deepcopy(value)
    modified["title"] = "Stale save must not replace this draft"
    unchanged("draft-storage-conflict", ("/api/authoring/drafts/" + value["id"], "POST", {"draft": modified, "expectedRevision": 0}), 409,
              lambda result: require(result.get("revision") == 1, "Conflict omitted current draft storage revision."))

    architecture = client.expect("/api/examples/mlp", "GET", None, 200)
    document = canvas(architecture)
    document["id"] = "m5-reliability"
    saved_document = client.expect("/api/documents/" + document["id"], "PUT", {"document": document, "expectedRevision": 0}, 200)
    modified_document = copy.deepcopy(document)
    modified_document["title"] = "Stale visual save"
    unchanged("canvas-storage-conflict", ("/api/documents/" + document["id"], "PUT", {"document": modified_document, "expectedRevision": 0}), 409,
              lambda result: require(result.get("revision") == 1, "Conflict omitted current canvas storage revision."))
    unchanged("invalid-export-format", ("/api/exports", "POST", {"document": document, "format": "jpeg", "dpi": 300}), 400,
              lambda result: require("svg/pdf/png" in result.get("error", ""), "Unsupported export was not explained."))

    registration = {key: architecture[key] for key in ("entry", "sources", "sourceDigest", "irDigest")}
    project = client.expect("/api/projects", "POST", registration, 201)
    target = next(node for node in project["architecture"]["nodes"] if node["kind"] == "Dropout")
    proposal_body = {"nodeId": target["id"], "parameter": "p", "value": 0.2,
                     "baseSourceDigest": project["sourceDigest"], "baseIrDigest": project["irDigest"]}
    stale = {**proposal_body, "baseSourceDigest": "0" * 64}
    unchanged("stale-semantic-binding", (f"/api/projects/{project['id']}/transactions", "POST", stale), 409,
              lambda result: require("reload" in result.get("error", ""), "Stale source rejection was not explained."))
    proposal = client.expect(f"/api/projects/{project['id']}/transactions", "POST", proposal_body, 200)
    require(proposal.get("status") == "ReviewReady" and "approvalId" not in proposal, "Proposal skipped concrete review.")
    unchanged("unapproved-source-commit", (f"/api/projects/{project['id']}/transactions/{proposal['id']}/commit", "POST", {"approvalId": "not-an-approval"}), 400,
              lambda result: require("approval" in result.get("error", ""), "Unapproved commit was not rejected."))
    require(client.expect(f"/api/projects/{project['id']}", "GET", None, 200)["sourceDigest"] == project["sourceDigest"], "Managed source changed.")
    write_json(output / "saved-draft.json", saved)
    write_json(output / "saved-canvas.json", saved_document)
    write_json(output / "unapproved-proposal.json", proposal)
    return {"checks": checks, "draft": saved, "document": saved_document, "project": project, "proposal": proposal}


def run_reliability(skill_directory: Path, output: Path, interpreter: Path | None = None) -> dict:
    installation = verify_install(skill_directory)
    skill, runtime = Path(installation["skillDirectory"]), Path(installation["runtimeRoot"])
    output = output.absolute()
    require(not output.exists() and not output.is_symlink(), "Output must be a new explicit directory.")
    require(not output.resolve().is_relative_to(skill), "Evidence/state must be outside installed Skill.")
    output.mkdir(parents=True, exist_ok=False)
    started = time.monotonic()
    result = {"schema": "archcanvas-m5-installed-reliability/1", "status": "running",
              "hostE2E": "not-tested", "modelExecution": False, "humanApproval": False,
              "sourceCommitted": False, "installation": installation, "checks": [], "serviceLifecycles": [],
              "scope": "installed-loopback-http-refusals-and-graceful-restart",
              "limitations": ["No browser gestures, video, novice/human trial or host-client workflow.",
                              "Restart is an owned service termination/restart; no disk-full, power-loss or platform-wide crash certification.",
                              "The probe never approves a semantic change or executes a model."]}
    state, working = output / "state", output / "unrelated-cwd"
    working.mkdir()
    command = [str(interpreter or Path(sys.executable)), "-I", "-B", str(skill / "scripts/archcanvas_runtime.py"),
               "serve", "--port", "0", "--data-dir", str(state / "documents"), "--studio-dir", str(runtime / "studio/dist")]

    def run_service(phase: str, operation):
        service = LocalService(command, working, output / f"service-{phase}.stderr.txt")
        try:
            with service:
                verify_origins(service.startup["capabilities"], runtime)
                client = FailureClient(service.url)
                client.token = client.expect("/api/session", "GET", None, 200)["token"]
                return operation(client)
        finally:
            result["serviceLifecycles"].append({"phase": phase, "pid": service.process.pid if service.process else None,
                                               "url": service.url, "exitCode": service.exit_code,
                                               "stopped": service.process is not None and service.process.poll() is not None})

    try:
        previous_token = None

        def first(client):
            nonlocal previous_token
            previous_token = client.token
            return exercise_refusals(client, state, output)

        fixtures_before = file_inventory(runtime / "fixtures")
        baseline = run_service("first", first)
        result["checks"].extend(baseline["checks"])

        def reopen(client):
            require(client.token != previous_token, "Restart did not rotate session token.")
            current = client.token
            client.token = previous_token
            before = file_inventory(state)
            rejected = client.expect("/api/authoring/validate", "POST", {"draft": draft()}, 403)
            require(file_inventory(state) == before, "Stale session wrote state.")
            write_json(output / "stale-session.json", {"httpStatus": 403, "body": rejected, "storageUnchanged": True})
            client.token = current
            require(client.expect("/api/authoring/drafts/" + draft()["id"], "GET", None, 200) == baseline["draft"], "Restart lost saved draft.")
            require(client.expect("/api/documents/m5-reliability", "GET", None, 200) == baseline["document"], "Restart lost canvas.")
            require(client.expect(f"/api/projects/{baseline['project']['id']}", "GET", None, 200) == baseline["project"], "Restart changed managed project.")
            proposal = client.expect(f"/api/projects/{baseline['project']['id']}/transactions/{baseline['proposal']['id']}", "GET", None, 200)
            require(proposal == baseline["proposal"], "Restart changed pending review.")
            # A fresh token still operates after the deliberately failed request.
            validated = client.expect("/api/authoring/validate", "POST", {"draft": draft()}, 200)
            require(validated.get("complete") is True and validated.get("tensors", {}).get("output") == {"shape": [2, 8], "dtype": "float32"}, "Fresh session did not recover.")
            result["checks"].append({"check": "restart-session-rotation-and-exact-persistence", "status": "passed", "httpStatus": 403})

        run_service("reopen", reopen)
        require(file_inventory(runtime / "fixtures") == fixtures_before, "Installed fixtures changed.")
        verify_install(skill)
        result["checks"].append({"check": "installed-inventory-and-fixtures-unchanged", "status": "passed"})
        result["status"] = "passed"
    except Exception as exc:
        result["status"], result["error"] = "failed", str(exc)
    finally:
        result["elapsedSeconds"] = round(time.monotonic() - started, 3)
        result["inputs"] = [{"path": str(path), "sha256": digest(path.read_bytes())}
                            for path in (Path(__file__).resolve(), Path(__file__).with_name("m5_host_smoke.py").resolve(),
                                         Path(__file__).with_name("m5_host_install.py").resolve())]
        write_json(output / "receipt.json", result)
    return result


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--skill-directory", type=Path, required=True)
    parser.add_argument("--output", type=Path, required=True)
    parser.add_argument("--python", type=Path, default=Path(sys.executable))
    args = parser.parse_args()
    try:
        result = run_reliability(args.skill_directory, args.output, args.python)
    except (OSError, ValueError) as exc:
        result = {"status": "failed", "error": str(exc), "hostE2E": "not-tested"}
    print(json.dumps(result, ensure_ascii=False, indent=2))
    return 0 if result["status"] == "passed" else 2


if __name__ == "__main__":
    raise SystemExit(main())
