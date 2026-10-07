#!/usr/bin/env python3
"""Exercise an installed project's CLI and HTTP service without a host/model run.

This is a package portability check, not a Codex/Claude/DSH client certificate.
It starts only its own loopback child, uses a separate explicit data directory,
prepares no approval, and stops its child even if startup or a check fails.
"""
from __future__ import annotations

import argparse
import copy
import hashlib
import json
from pathlib import Path
import queue
import re
import subprocess
import sys
import threading
import time
import xml.etree.ElementTree as ET
from urllib.parse import urlsplit
from urllib.request import ProxyHandler, Request, build_opener


def digest(data: bytes) -> str:
    return hashlib.sha256(data).hexdigest()


def write_json(path: Path, value: object) -> None:
    path.write_text(json.dumps(value, ensure_ascii=False, indent=2, allow_nan=False) + "\n", encoding="utf-8")


def require(condition: bool, message: str) -> None:
    if not condition:
        raise ValueError(message)


def verify_origins(capabilities: dict, runtime: Path) -> None:
    provenance = capabilities.get("packageProvenance", {})
    require(provenance.get("independent") is True, "Runtime independence is not established.")
    modules = provenance.get("modules")
    require(isinstance(modules, dict) and bool(modules), "Package origins are missing.")
    for name, value in modules.items():
        require(isinstance(value, str) and Path(value).is_file(), f"Missing package origin: {name}")
        require(Path(value).resolve().is_relative_to(runtime / "src"), f"Package outside installed runtime: {name}")
    require(Path(provenance.get("projectRoot", "")).resolve() == runtime, "Wrong project root.")


def loopback_url(value: object) -> str:
    require(isinstance(value, str), "Service must return a URL.")
    parsed = urlsplit(value)
    require(parsed.scheme == "http" and parsed.hostname == "127.0.0.1" and
            parsed.username is None and parsed.password is None and
            parsed.path in ("", "/") and not parsed.query and not parsed.fragment and
            parsed.port is not None and 0 < parsed.port < 65536,
            "Service did not return its loopback origin.")
    return value.rstrip("/")


class LocalService:
    def __init__(self, command: list[str], cwd: Path, stderr: Path, timeout: float = 20):
        self.command, self.cwd, self.stderr_path, self.timeout = command, cwd, stderr, timeout
        self.process: subprocess.Popen | None = None
        self.exit_code: int | None = None
        self.url: str | None = None
        self.startup: dict | None = None

    def __enter__(self):
        self.stderr_stream = self.stderr_path.open("xb")
        try:
            self.process = subprocess.Popen(self.command, cwd=self.cwd, stdout=subprocess.PIPE,
                                            stderr=self.stderr_stream, text=True, encoding="utf-8")
            lines: queue.Queue = queue.Queue()

            def read_startup():
                try:
                    lines.put(self.process.stdout.readline(1024 * 1024))
                except Exception as exc:
                    lines.put(exc)

            self.reader = threading.Thread(target=read_startup, daemon=True)
            self.reader.start()
            line = lines.get(timeout=self.timeout)
            if isinstance(line, Exception):
                raise line
            require(bool(line), "Service exited before reporting startup.")
            self.startup = json.loads(line)
            require(isinstance(self.startup, dict), "Invalid service startup response.")
            self.url = loopback_url(self.startup.get("url"))
            require(self.process.poll() is None, "Service already stopped.")
            return self
        except Exception:
            self.stop()
            raise

    def stop(self):
        if self.process is not None:
            if self.process.poll() is None:
                self.process.terminate()
                try:
                    self.process.wait(timeout=5)
                except subprocess.TimeoutExpired:
                    self.process.kill()
                    self.process.wait(timeout=5)
            self.exit_code = self.process.returncode
            if self.process.stdout:
                self.process.stdout.close()
        if hasattr(self, "reader"):
            self.reader.join(timeout=1)
        if hasattr(self, "stderr_stream"):
            self.stderr_stream.close()

    def __exit__(self, *args):
        self.stop()


class Client:
    def __init__(self, url: str):
        self.url = loopback_url(url)
        self.opener = build_opener(ProxyHandler({}))
        self.token: str | None = None

    def request(self, path: str, method="GET", body=None):
        require(path.startswith("/") and not path.startswith("//") and "://" not in path,
                "Only relative API paths are allowed.")
        headers = {"Content-Type": "application/json"}
        if self.token is not None:
            headers["X-ArchCanvas-Session"] = self.token
        req = Request(self.url + path, method=method, headers=headers,
                      data=json.dumps(body, allow_nan=False).encode() if body is not None else None)
        with self.opener.open(req, timeout=20) as response:
            return response.status, response.read(), dict(response.headers)

    def json(self, path: str, method="GET", body=None, status=200):
        code, raw, _ = self.request(path, method, body)
        require(code == status, f"Unexpected HTTP status for {path}: {code}")
        return json.loads(raw)


def canvas(architecture: dict) -> dict:
    roots = [node["id"] for node in architecture["nodes"] if not node.get("parentId")]
    selected = next(node for node in architecture["nodes"] if node["kind"] == "Input")
    return {
        "schemaVersion": 1, "id": "m5-package-portability", "title": "M5 installed runtime smoke",
        "revision": 1, "sourceBindingDigest": architecture["sourceDigest"],
        "architecture": copy.deepcopy(architecture),
        "displayAliases": {selected["id"]: "Installed input"}, "nodeStyleOverrides": {}, "edgeStyleOverrides": {},
        "legendItems": [{"id": "smoke-legend", "label": "Installed runtime", "color": "#345678", "glyph": "module"}],
        "annotations": [], "pageSpec": {"widthMm": 180, "background": "#ffffff", "preset": "paper"},
        "expandedIds": roots, "layout": {}, "layoutByFrontier": {}, "pinnedObjects": [],
    }


def run_smoke(skill_directory: Path, output: Path, interpreter: Path | None = None) -> dict:
    from m5_host_install import verify_install

    installation = verify_install(skill_directory)
    skill = Path(installation["skillDirectory"])
    runtime = Path(installation["runtimeRoot"])
    output = output.absolute()
    require(not output.exists() and not output.is_symlink(), "Output must be a new explicit directory.")
    require(not output.resolve().is_relative_to(skill), "Smoke evidence must be outside installed Skill.")
    output.mkdir(parents=True, exist_ok=False)
    started = time.monotonic()
    result = {"schema": "archcanvas-m5-installed-cli-http-smoke/1", "status": "running",
              "scope": "package-installation-cli-http", "hostE2E": "not-tested", "modelExecution": False,
              "humanApproval": False, "skillDirectory": str(skill), "runtimeRoot": str(runtime),
              "installation": installation, "checks": [], "serviceLifecycles": [],
              "limits": ["The canvas is constructed by this HTTP probe; it does not prove browser gesture, undo, or novice usability.",
                         "Host Skill discovery and model prompt loading are separate from CLI/HTTP package portability.",
                         "Only SVG is exercised here; PDF/PNG dependencies, font fidelity, physical review and host E2E remain separate."]}
    working = output / "unrelated-cwd"
    working.mkdir()
    # Never run a command supplied by mutable metadata. These argv are fixed.
    command = [str(interpreter or Path(sys.executable)), "-I", "-B", str(skill / "scripts/archcanvas_runtime.py")]

    def checked_cli(args, filename):
        proc = subprocess.run(command + args, cwd=working, capture_output=True, text=True, timeout=30)
        (output / (filename + ".stderr.txt")).write_text(proc.stderr)
        require(proc.returncode == 0, f"CLI failed: {args[0]} ({proc.returncode}): {proc.stderr[:300]}")
        value = json.loads(proc.stdout)
        write_json(output / (filename + ".json"), value)
        result["checks"].append({"check": filename, "status": "passed", "exitCode": 0})
        return value

    try:
        caps = checked_cli(["capabilities"], "cli-capabilities")
        verify_origins(caps, runtime)
        fixture = runtime / "fixtures/mlp"
        source_before = digest((fixture / "model.py").read_bytes())
        architecture = checked_cli(["analyze", "--root", str(fixture), "--entry", "model:MLP"], "cli-analysis")
        document = canvas(architecture)
        write_json(output / "document.json", document)
        data_dir = output / "state/documents"
        serve = command + ["serve", "--port", "0", "--data-dir", str(data_dir), "--studio-dir", str(runtime / "studio/dist")]
        first = LocalService(serve, working, output / "service-first.stderr.txt")
        try:
            with first as service:
                verify_origins(service.startup["capabilities"], runtime)
                client = Client(service.url)
                client.token = client.json("/api/session")["token"]
                code, html, _ = client.request("/")
                require(code == 200, "Studio did not load.")
                (output / "studio-index.html").write_bytes(html)
                asset_paths = re.findall(r'(?:src|href)="(/assets/[^"\s]+)"', html.decode())
                require(bool(asset_paths), "Studio asset references missing.")
                assets = []
                for path in asset_paths:
                    status, raw, _ = client.request(path)
                    require(status == 200 and raw == (runtime / "studio/dist" / path.lstrip("/")).read_bytes(), "Wrong Studio asset bytes.")
                    assets.append({"path": path, "sha256": digest(raw), "bytes": len(raw)})
                result["studioAssets"] = assets
                result["checks"].append({"check": "installed-studio-assets", "status": "passed"})
                fetched = client.json("/api/examples/mlp")
                require(fetched["irDigest"] == architecture["irDigest"] and fetched["sourceDigest"] == architecture["sourceDigest"], "Example did not use installed source.")
                payload = {key: architecture[key] for key in ("entry", "sources", "sourceDigest", "irDigest")}
                project = client.json("/api/projects", "POST", payload, status=201)
                require(project["scope"] == "managed-copy", "Project is not a managed copy.")
                drop = next(node for node in project["architecture"]["nodes"] if node["kind"] == "Dropout")
                proposal = client.json(f"/api/projects/{project['id']}/transactions", "POST", {
                    "nodeId": drop["id"], "parameter": "p", "value": 0.2,
                    "baseSourceDigest": project["sourceDigest"], "baseIrDigest": project["irDigest"]})
                require(proposal["status"] == "ReviewReady" and "approvalId" not in proposal, "Proposal skipped review.")
                write_json(output / "unapproved-proposal.json", proposal)
                unchanged = client.json(f"/api/projects/{project['id']}")
                require(unchanged["sourceDigest"] == project["sourceDigest"] and unchanged["irDigest"] == project["irDigest"], "Proposal changed managed source.")
                result["checks"].append({"check": "managed-proposal-unapproved-source-unchanged", "status": "passed"})
                saved = client.json("/api/documents/" + document["id"], "PUT", {"document": document, "expectedRevision": 0})
                write_json(output / "saved.json", saved)
                require(saved["document"] == document and saved["revision"] == 1, "Saved document differs.")
                export = client.json("/api/exports", "POST", {"document": document, "format": "svg", "dpi": 300}, status=201)
                write_json(output / "export-receipt.json", export)
                artifact_path = export["url"]
                _, svg, headers = client.request(artifact_path)
                require(b"<svg" in svg and headers.get("Content-Type", "").startswith("image/svg+xml"), "SVG artifact invalid.")
                figure = ET.fromstring(svg)
                require(figure.tag == "{http://www.w3.org/2000/svg}svg" and figure.get("width") == "180mm", "SVG physical width differs.")
                texts = ["".join(node.itertext()) for node in figure.iter("{http://www.w3.org/2000/svg}text")]
                require("Installed input" in texts and "Installed runtime" in texts, "Export did not preserve current alias/legend.")
                require(export["receipt"]["sourceDigest"] == architecture["sourceDigest"] and
                        export["receipt"]["irDigest"] == architecture["irDigest"] and
                        export["receipt"]["revision"] == document["revision"], "Export bindings differ.")
                (output / "installed-180.svg").write_bytes(svg)
                result["artifact"] = {"path": "installed-180.svg", "sha256": digest(svg), "bytes": len(svg), "format": "svg"}
                result["checks"].append({"check": "current-document-svg", "status": "passed"})
        finally:
            result["serviceLifecycles"].append({"phase": "first", "pid": first.process.pid if first.process else None, "url": first.url, "exitCode": first.exit_code, "stopped": first.process is not None and first.process.poll() is not None})
        second = LocalService(serve, working, output / "service-reopen.stderr.txt")
        try:
            with second as service:
                client = Client(service.url)
                reopened = client.json("/api/documents/" + document["id"])
                require(reopened == saved, "Restart did not preserve saved document exactly.")
                write_json(output / "reopened.json", reopened)
                project_again = client.json(f"/api/projects/{project['id']}")
                require(project_again["sourceDigest"] == project["sourceDigest"], "Restart changed managed source.")
                _, restored, _ = client.request(artifact_path)
                require(restored == svg, "Export artifact did not survive restart.")
                result["checks"].append({"check": "service-restart-document-project-export-persistence", "status": "passed"})
        finally:
            result["serviceLifecycles"].append({"phase": "reopen", "pid": second.process.pid if second.process else None, "url": second.url, "exitCode": second.exit_code, "stopped": second.process is not None and second.process.poll() is not None})
        require(digest((fixture / "model.py").read_bytes()) == source_before, "Installed fixture source changed.")
        verify_install(skill)
        result["checks"].append({"check": "installed-inventory-and-fixture-unchanged", "status": "passed"})
        result["status"] = "passed"
    except Exception as exc:
        result["status"] = "failed"
        result["error"] = str(exc)
    finally:
        result["elapsedSeconds"] = round(time.monotonic() - started, 3)
        result["inputs"] = [{"path": str(path), "sha256": digest(path.read_bytes())}
                            for path in (Path(__file__).resolve(), Path(__file__).with_name("m5_host_install.py").resolve())]
        write_json(output / "receipt.json", result)
    return result


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--skill-directory", type=Path, required=True)
    parser.add_argument("--output", type=Path, required=True)
    parser.add_argument("--python", type=Path, default=Path(sys.executable))
    args = parser.parse_args()
    try:
        result = run_smoke(args.skill_directory, args.output, args.python)
    except (OSError, ValueError) as exc:
        result = {"status": "failed", "error": str(exc), "hostE2E": "not-tested"}
    print(json.dumps(result, ensure_ascii=False, indent=2))
    return 0 if result["status"] == "passed" else 2


if __name__ == "__main__":
    raise SystemExit(main())
