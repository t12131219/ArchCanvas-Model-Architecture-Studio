"""Independent synthetic adversarial checks; writes only to a temporary tree.

The fixture below is intentionally tiny. It checks archive/install contracts,
not the real distribution payload, host E2E, model execution or human review.
"""
from __future__ import annotations

import hashlib
import importlib.util
import io
import json
from pathlib import Path
import sys
import tarfile
import tempfile

ROOT = Path(__file__).resolve().parents[3]
INPUT_PATHS = [ROOT / "scripts/m5_beta_bundle.py", ROOT / "scripts/check_m5_beta_release.py", ROOT / "schemas/m5-beta-release.schema.json", Path(__file__)]
INPUT_BYTES = {path: path.read_bytes() for path in INPUT_PATHS}
SPEC = importlib.util.spec_from_file_location("independent_m5_bundle", ROOT / "scripts/m5_beta_bundle.py")
sys.path.insert(0, str(ROOT / "scripts"))
PRODUCT = importlib.util.module_from_spec(SPEC)
SPEC.loader.exec_module(PRODUCT)


def encode(value):
    return (json.dumps(value, ensure_ascii=False, indent=2, sort_keys=True) + "\n").encode()


def sha(data):
    return hashlib.sha256(data).hexdigest()


def metadata(contents, version="0.1.0-beta.1"):
    return {
        "schemaVersion": 1, "product": "archcanvas", "kind": "local-beta-preview",
        "version": version, "releaseMetadataVersion": version, "status": "in_progress",
        "gates": {"m4": "partial", "m5": "in_progress"},
        "hostE2E": {"codex": "not-tested", "claude-code": "not-tested", "deepseek-harness": "not-tested"},
        "dependenciesBundled": False, "modelExecution": False,
        "releaseManifestSha256": sha(contents["docs/evidence/m5-beta-release-manifest.json"]),
        "files": [{"path": name, "sha256": sha(raw), "bytes": len(raw)} for name, raw in contents.items()],
    }


def archive(path, manifest, contents, members=None):
    with tarfile.open(path, "w:gz") as tar:
        if members is not None:
            for member, data in members:
                tar.addfile(member, io.BytesIO(data) if data is not None else None)
            return
        for name, raw in {**contents, "BUNDLE-MANIFEST.json": encode(manifest)}.items():
            info = tarfile.TarInfo(f"archcanvas-{manifest['version']}/{name}")
            info.size = len(raw)
            tar.addfile(info, io.BytesIO(raw))


def rejected(action):
    try:
        action()
    except ValueError as exc:
        return str(exc)
    raise AssertionError("unsafe input was accepted")


def main():
    records = []
    def case(name, action):
        try:
            detail = action()
            records.append({"name": name, "status": "passed", "detail": detail})
        except Exception as exc:
            records.append({"name": name, "status": "failed", "error": f"{type(exc).__name__}: {exc}"})

    release = {
        "schemaVersion": 1, "releaseId": "archcanvas-m5-beta-0.1.0-beta.1", "releaseVersion": "0.1.0-beta.1",
        "stage": "M5-beta", "status": "in_progress", "generatedAt": "2026-10-07",
        "build": {"gitCommit": "a" * 40, "workingTree": "dirty-uncommitted", "studioPackageVersion": "0.1.0", "runtimeSource": "formal-project", "prototypeDependency": "forbidden"},
        "artifacts": [{"path": "dummy.txt", "sha256": sha(b"original"), "role": "skill"}],
        "hostMatrix": [{"host": host, "contractStatus": "unreviewed", "discovery": ["synthetic-only"], "studio": "unavailable", "e2e": "not-tested", "limitations": ["Synthetic test fixture"]} for host in ("codex", "claude-code", "deepseek-harness")],
        "knownLimitations": ["Synthetic fixture only; no host or product acceptance"], "gates": {"m4": "partial", "m5": "in_progress"},
    }
    contents = {"dummy.txt": b"original", "schemas/m5-beta-release.schema.json": (ROOT / "schemas/m5-beta-release.schema.json").read_bytes(),
                "docs/evidence/m5-beta-release-manifest.json": encode(release)}
    # Required filenames are opaque placeholders in this safety-only fixture;
    # no placeholder is imported or executed and no real bundle is claimed.
    for name in ("README.md", "AGENTS.md", "THIRD_PARTY_NOTICES.md", "pyproject.toml", "requirements.lock", "requirements-runtime.lock",
                 "studio/package.json", "studio/package-lock.json", "studio/tsconfig.json", "studio/vite.config.ts", "studio/index.html",
                 "docs/m5-beta-release.md", "docs/capability-matrix.md", "docs/m4-routing-user-simulation-v2.md", "docs/m5-demo-export.md",
                 "scripts/check_m5_beta_release.py", "scripts/m5_beta_bundle.py", "scripts/m5_beta_preflight.py", "scripts/export_canvas.mjs",
                 "tests/test_m5_beta_release.py", "tests/test_m5_beta_bundle.py", "tests/test_m5_beta_preflight.py"):
        contents[name] = b"Opaque synthetic payload; never executed.\n"
    manifest = metadata(contents)
    with tempfile.TemporaryDirectory(prefix="archcanvas-m5-independent-") as temporary:
        work = Path(temporary)
        good = work / "good.tar.gz"
        archive(good, manifest, contents)
        for label, member_name, member_type in (
            ("parent-traversal", "archcanvas-0.1.0-beta.1/../escape", tarfile.REGTYPE),
            ("absolute-path", "/tmp/escape", tarfile.REGTYPE),
            ("symbolic-link", "archcanvas-0.1.0-beta.1/link", tarfile.SYMTYPE),
            ("hard-link", "archcanvas-0.1.0-beta.1/link", tarfile.LNKTYPE),
        ):
            member = tarfile.TarInfo(member_name)
            member.type, member.linkname = member_type, "../../escape"
            member.size = 1 if member_type == tarfile.REGTYPE else 0
            path = work / f"{label}.tar.gz"
            archive(path, manifest, {}, [(member, b"x" if member_type == tarfile.REGTYPE else None)])
            case(f"archive rejects {label}", lambda path=path: rejected(lambda: PRODUCT.read_bundle(path)))

        malformed = [[], {**manifest, "version": 1}, {**manifest, "files": [[]]},
                     {**manifest, "files": [{"path": "dummy.txt", "sha256": sha(b"original"), "bytes": True}]}]
        for index, value in enumerate(malformed):
            path = work / f"malformed-{index}.tar.gz"
            raw = encode(value)
            member = tarfile.TarInfo("archcanvas-0.1.0-beta.1/BUNDLE-MANIFEST.json"); member.size = len(raw)
            archive(path, manifest, {}, [(member, raw)])
            case(f"manifest malformed shape {index} is cleanly rejected", lambda path=path: rejected(lambda: PRODUCT.read_bundle(path)))

        forged = {**manifest, "hostE2E": {host: "passed" for host in ("codex", "claude-code", "deepseek-harness")}}
        path = work / "forged-host.tar.gz"; archive(path, forged, contents)
        case("archive cannot claim three-host E2E", lambda: rejected(lambda: PRODUCT.read_bundle(path)))

        for label, schema_raw in (("top-level-array", b"[]"), ("invalid-type-array", b'{"type": []}')):
            bad_contents = {**contents, "schemas/m5-beta-release.schema.json": schema_raw}
            path = work / f"bad-schema-{label}.tar.gz"; archive(path, metadata(bad_contents), bad_contents)
            case(f"inner schema {label} is cleanly rejected", lambda path=path: rejected(lambda: PRODUCT.read_bundle(path)))

        bad_release = {**release, "hostMatrix": [{**row, "e2e": "passed"} for row in release["hostMatrix"]]}
        bad_contents = {**contents, "schemas/m5-beta-release.schema.json": b"{}", "docs/evidence/m5-beta-release-manifest.json": encode(bad_release)}
        path = work / "weakened-schema-host.tar.gz"; archive(path, metadata(bad_contents), bad_contents)
        case("weakening inner schema cannot forge three-host E2E", lambda: rejected(lambda: PRODUCT.read_bundle(path)))

        prefix = work / "installed"
        PRODUCT.install(good, prefix)
        installed = prefix / "releases/0.1.0-beta.1"
        raw_original = (installed / "dummy.txt").read_bytes()
        def modified_installed():
            (installed / "BUNDLE-MANIFEST.json").write_bytes(encode(forged))
            try:
                return rejected(lambda: PRODUCT.activate(prefix, "0.1.0-beta.1"))
            finally:
                (installed / "BUNDLE-MANIFEST.json").write_bytes(encode(manifest))
        case("installed metadata cannot claim three-host E2E", modified_installed)

        def user_current():
            (prefix / "current").symlink_to(work / "user-original")
            try:
                result = rejected(lambda: PRODUCT.activate(prefix, "0.1.0-beta.1"))
                assert (prefix / "current").is_symlink()
                assert (prefix / "current").readlink() == work / "user-original"
                return result
            finally:
                (prefix / "current").unlink()
        case("unknown current symlink is not replaced", user_current)

        def user_activation():
            state = prefix / "activation.json"; state.write_bytes(b"user original bytes")
            try:
                result = rejected(lambda: PRODUCT.activate(prefix, "0.1.0-beta.1"))
                assert state.read_bytes() == b"user original bytes"
                assert not (prefix / "current").is_symlink()
                return result
            finally:
                state.unlink()
        case("user activation file is not overwritten", user_activation)

        def user_temp():
            original = work / "user-temp-target"; original.write_bytes(b"user original bytes")
            stale = prefix / ".activation-next.json"; stale.symlink_to(original)
            try:
                result = rejected(lambda: PRODUCT.activate(prefix, "0.1.0-beta.1"))
                assert original.read_bytes() == b"user original bytes"
                assert stale.is_symlink()
                assert not (prefix / "current").is_symlink()
                return result
            finally:
                stale.unlink()
        case("stale activation temporary symlink cannot overwrite target", user_temp)

        def invalid_inner_release():
            bad_release = {**release, "build": {**release["build"], "runtimeSource": "forbidden-other-tree"}}
            bad_contents = {**contents, "docs/evidence/m5-beta-release-manifest.json": encode(bad_release)}
            path = work / "bad-inner.tar.gz"; archive(path, metadata(bad_contents), bad_contents)
            bad_prefix = work / "bad-inner-prefix"
            detail = rejected(lambda: PRODUCT.install(path, bad_prefix))
            assert not (bad_prefix / "releases/0.1.0-beta.1").exists(), "failed install left a final version directory"
            assert not (bad_prefix / "current").is_symlink()
            return detail
        case("failed inner-release validation leaves no installed version", invalid_inner_release)

        def path_collision():
            collision_contents = {"foo": b"x", "foo/bar": b"y", **contents}
            path = work / "prefix-collision.tar.gz"; archive(path, metadata(collision_contents), collision_contents)
            return rejected(lambda: PRODUCT.read_bundle(path))
        case("archive rejects file/directory prefix collision before extraction", path_collision)

        def injected_staging_failure():
            bad_prefix = work / "injected-failure-prefix"
            sibling = bad_prefix / "releases/user-original"
            sibling.mkdir(parents=True); (sibling / "note.txt").write_bytes(b"user original bytes")
            original_verify = PRODUCT.verify_directory
            def refuse(_directory):
                raise ValueError("Independent injected staging verification failure")
            PRODUCT.verify_directory = refuse
            try:
                detail = rejected(lambda: PRODUCT.install(good, bad_prefix))
            finally:
                PRODUCT.verify_directory = original_verify
            assert (sibling / "note.txt").read_bytes() == b"user original bytes"
            assert not (bad_prefix / "releases/0.1.0-beta.1").exists()
            assert not list((bad_prefix / "releases").glob(".install-*"))
            return detail
        case("failed staging removes only its own temporary tree", injected_staging_failure)

        def upgrade_rollback():
            PRODUCT.activate(prefix, "0.1.0-beta.1")
            second_release = {**release, "releaseVersion": "0.1.0-beta.2", "releaseId": "archcanvas-m5-beta-0.1.0-beta.2"}
            second_contents = {**contents, "docs/evidence/m5-beta-release-manifest.json": encode(second_release)}
            second = work / "second.tar.gz"; second_manifest = metadata(second_contents, "0.1.0-beta.2")
            archive(second, second_manifest, second_contents)
            PRODUCT.install(second, prefix, True)
            assert (prefix / "current").resolve() == prefix / "releases/0.1.0-beta.2"
            PRODUCT.activate(prefix, "0.1.0-beta.1")
            assert (prefix / "current").resolve() == installed
            assert (installed / "dummy.txt").read_bytes() == raw_original
            assert (prefix / "releases/0.1.0-beta.2/dummy.txt").read_bytes() == raw_original
            return "Both immutable version payloads preserved through upgrade and rollback; current points to the first version."
        case("upgrade and rollback preserve both version payloads", upgrade_rollback)

    unchanged = all(path.read_bytes() == raw for path, raw in INPUT_BYTES.items())
    report = {"schema": "archcanvas-m5-independent-safety-audit/1", "role": "Independent AI read-only product review; synthetic fixtures written only in temporary directories",
              "inputs": [{"path": str(path.relative_to(ROOT)), "bytes": len(raw), "sha256": sha(raw)} for path, raw in INPUT_BYTES.items()],
              "inputsUnchangedDuringAudit": unchanged,
              "status": "passed" if unchanged and all(record["status"] == "passed" for record in records) else "failed",
              "passed": sum(record["status"] == "passed" for record in records), "total": len(records), "cases": records,
              "limits": ["Synthetic minimum payload verifies safety contracts, not completeness of the real release archive.", "No host E2E, human participant, model execution, publication or public release is certified."]}
    print(json.dumps(report, ensure_ascii=False, indent=2))
    return 0 if report["status"] == "passed" else 1


if __name__ == "__main__":
    raise SystemExit(main())
