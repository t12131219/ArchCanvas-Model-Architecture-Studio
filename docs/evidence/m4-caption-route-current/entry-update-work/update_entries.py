"""Prepare reviewable current headers; apply only final, source-bound facts.

This is documentation tooling. It imports no product code and never modifies
historical evidence or a research package. The default action writes previews.
"""
from argparse import ArgumentParser
from datetime import datetime, timezone
import difflib
import hashlib
import json
from pathlib import Path
import re
from urllib.parse import unquote


HERE = Path(__file__).resolve().parent
ROOT = HERE.parents[3]
ARCHIVE_PATH = "docs/evidence/m4-caption-route-current/before-change/manifest.json"
STAGE_PATH = "docs/m4-caption-association-shortcuts.md"
GATE_PATH = "docs/evidence/m4-current-gate-audit.json"
ENTRY_PATHS = [
    "README.md", "docs/acceptance.md", "docs/capability-matrix.md",
    "docs/evidence/README.md", "docs/m4-ai-usability-audit.md",
    "docs/m4-completion.md", "docs/m4-exit-audit.md",
    "docs/m4-human-review-handoff.md", "docs/m4-performance.md",
    "docs/m4-research-protocol.md", "skills/archcanvas/references/formal-alpha.md",
    "skills/archcanvas/references/runtime-compatibility.md",
    "skills/archcanvas/references/visual-workflow.md",
]
VISUAL_INTRO = (
    "Use this reference for figure creation, visual refinement, expansion, and "
    "export. These are acceptance contracts for a compatible Studio, not assertions "
    "that every installed runtime supports them. Check operations before invoking them."
)


def read_json(path):
    return json.loads(path.read_bytes())


def binding(path):
    raw = path.read_bytes()
    return {"path": str(path.relative_to(ROOT)), "bytes": len(raw),
            "sha256": hashlib.sha256(raw).hexdigest()}


def split_entry(text):
    sections = list(re.finditer(r"^## ", text, re.M))
    if len(sections) < 2:
        raise ValueError("Entry has fewer than two level-2 sections")
    return text[:sections[0].start()], text[sections[1].start():]


def relative_link(source, target):
    import os
    return os.path.relpath(ROOT / target, (ROOT / source).parent)


def render_header(template, source, targets):
    text = template
    for name, target in targets.items():
        text = text.replace("{{" + name + "}}", relative_link(source, target))
    if "{{" in text or "}}" in text:
        raise ValueError("Unresolved header substitution in " + source)
    return text.rstrip() + "\n\n"


def check_markdown_links(source_path, text):
    rows = []
    for target in re.findall(r"!?\[[^\]]*\]\(([^\)]+)\)", text):
        cleaned = target.strip().removeprefix("<").removesuffix(">")
        if re.match(r"(?:[a-zA-Z][a-zA-Z0-9+.-]*:|#)", cleaned):
            continue
        local = unquote(cleaned.split("#")[0].split("?")[0])
        path = ((ROOT / source_path).parent / local).resolve()
        rows.append({"from": source_path, "target": target,
                     "exists": path.exists(), "resolved": str(path)})
    return rows


def validate_facts(facts, old_gate):
    """Reject unbound green numbers, unavailable files and widened claims."""
    receipt = read_json(ROOT / facts["buildReceipt"])
    assert receipt["inputsUnchanged"] is True
    assert receipt["publicationInputsUnchanged"] is True
    assert all(check["exitCode"] == 0 for check in receipt["checks"])
    for item in receipt["inputs"] + receipt["build"] + receipt["publicationInputs"]:
        actual = binding(ROOT / item["path"])
        assert actual == {key: item[key] for key in ("path", "bytes", "sha256")}, item["path"]
    gate = facts["finalGate"]
    assert gate["overall"] == "partial" and gate["m5"] == "not_started"
    assert gate["humanParticipants"] == 0
    assert gate["currentStage"] == STAGE_PATH
    assert gate["currentEntryPreChangeArchive"] == ARCHIVE_PATH
    assert gate["build"]["checks"] == facts["buildReceipt"]
    assert gate["build"]["sourceTestConfigBindings"] == len(receipt["inputs"])
    assert gate["build"]["distBindings"] == len(receipt["build"])
    assert gate["build"]["totalSourceBuildBindings"] == len(receipt["inputs"]) + len(receipt["build"])
    assert gate["build"]["strictBuildExitCode"] == 0
    assert gate["build"]["skipped"] == gate["build"]["publicationSkipped"] == 0
    checks = {item["label"]: item for item in receipt["checks"]}
    studio_log = (ROOT / checks["studio"]["log"]).read_text()
    suite = {name: int(value) for name, value in
             re.findall(r"^ℹ (tests|pass|fail|cancelled|skipped|todo) (\d+)$", studio_log, re.M)}
    assert suite["tests"] == suite["pass"] == gate["build"]["studioTests"]
    assert suite["fail"] == suite["cancelled"] == suite["skipped"] == suite["todo"] == 0
    publication_log = (ROOT / checks["publication"]["log"]).read_text()
    publication_count = re.findall(r"^Ran (\d+) tests? in ", publication_log, re.M)
    assert len(publication_count) == 1 and int(publication_count[0]) == gate["build"]["publicationTests"]
    assert publication_log.rstrip().endswith("OK")
    assets = [Path(item["path"]).name for item in receipt["build"]]
    assert gate["build"]["js"] in assets and gate["build"]["css"] in assets
    old_reqs = {item["id"]: item for item in old_gate["requirements"]}
    reqs = {item["id"]: item for item in gate["requirements"]}
    assert set(reqs) == set(old_reqs)
    for key in ("base-models", "semantic-holdout", "shared-repeat-opaque"):
        assert reqs[key] == old_reqs[key], key
    assert reqs["research-task"]["status"] == reqs["publication-review"]["status"] == "not_done"
    assert reqs["browser-performance"]["status"] == "failed_or_unverified"
    assert gate["aiSimulatedRoles"] == old_gate["aiSimulatedRoles"]
    assert gate["historicalBtwBuild"] == old_gate["build"]
    for old_name, historical_name, req_id in (
        ("observedCurrentCaption", "observedHistoricalBtwCaption", "visual-authoring"),
        ("observedCurrentBtw7", "observedHistoricalBtw7", "browser-performance"),
        ("observedCurrentExportPreflight", "observedHistoricalBtwExportPreflight", "publication-review"),
    ):
        assert reqs[req_id][historical_name] == old_reqs[req_id][old_name], historical_name
    # Every gate evidence path must be a real file. Readiness is not human data.
    for req in gate["requirements"]:
        for path in req["evidence"]:
            assert (ROOT / path).is_file(), path
    research = gate["currentResearchPackage"]
    assert research["humans"] == research["assigned"] == research["collected"] == 0
    assert not research["servicesStarted"] and not research["portsAvailabilityChecked"]
    package = ROOT / research["path"]
    assert binding(package / "manifest.json")["sha256"] == research["manifestSha256"]
    manifest = read_json(package / "manifest.json")
    assert len(manifest["slots"]) == research["pristineSlots"] == 5
    assert [slot["port"] for slot in manifest["slots"]] == research["registeredPorts"]
    assert all(slot["participantCode"] is None and slot["assignment"] == "unassigned" for slot in manifest["slots"])
    return receipt


def main():
    parser = ArgumentParser(description=__doc__)
    parser.add_argument("facts", type=Path, help="Final facts/prose and complete current gate JSON")
    parser.add_argument("--output", type=Path, required=True, help="New, non-existing preview/report directory")
    parser.add_argument("--basis-report", type=Path, help="Previously applied current entry bindings for a reviewed documentation-only correction")
    parser.add_argument("--apply", action="store_true", help="Apply already reviewable generated current headers/gate")
    args = parser.parse_args()
    args.facts = args.facts.resolve()
    args.output = args.output.resolve()
    assert not args.output.exists(), "Never overwrite a previous attempt"
    facts = read_json(args.facts)
    assert facts["status"] == "final_facts_ready", "Draft facts cannot update current entries"
    archive = read_json(ROOT / ARCHIVE_PATH)
    assert len(archive["inputs"]) == 126
    originals = {row["path"]: row for row in archive["inputs"]}
    for row in archive["inputs"]:
        actual = binding(ROOT / row["snapshot"])
        assert actual["sha256"] == row["sha256"] and actual["bytes"] == row["bytes"]
    old_gate = read_json(ROOT / originals[GATE_PATH]["snapshot"])
    basis = read_json(args.basis_report.resolve()) if args.basis_report else None
    if basis:
        assert basis["status"] == "applied"
        expected_current = {row["path"]: row["currentSha256"] for row in basis["updatedEntries"]}
        assert set(expected_current) == set(ENTRY_PATHS)
    validate_facts(facts, old_gate)
    args.output.mkdir(parents=True)
    targets = {"stage": STAGE_PATH, "gate": GATE_PATH, "archive": ARCHIVE_PATH,
               "checks": facts["buildReceipt"], "browser": facts["browserReceipt"],
               "independent": facts["independentReceipt"], "research": facts["researchReadiness"],
               "exports": "docs/evidence/m4-caption-route-current/browser-export-final/report.json"}
    updates, links = [], []
    for source in ENTRY_PATHS:
        row = originals[source]
        old = (ROOT / row["snapshot"]).read_text()
        if basis:
            assert binding(ROOT / source)["sha256"] == expected_current[source], "Uncoordinated current entry change: " + source
        else:
            assert (ROOT / source).read_bytes() == (ROOT / row["snapshot"]).read_bytes(), "Uncoordinated entry change: " + source
        preamble, history = split_entry(old)
        language = "en" if source.startswith("skills/") else "cn"
        header = render_header(facts["headers"][language], source, targets)
        assert len(list(re.finditer(r"^## ", header, re.M))) == 1
        boundary_tokens = ["partial", "not_started", "humans 0", "AI is not a human participant", "not presented FPS", "no generated model was executed"] if language == "en" else ["partial", "not_started", "真人 0", "AI 不计真人", "不是实际呈现 FPS", "未执行生成模型"]
        assert all(token in header for token in boundary_tokens), "Missing scope boundary: " + source
        if source == "skills/archcanvas/references/visual-workflow.md":
            header += VISUAL_INTRO + "\n\n"
        if source == "docs/m4-research-protocol.md":
            header += render_header(facts["researchCommandSection"], source, targets)
        current = preamble + header + history
        assert split_entry(current)[1] == history, "Historical body changed: " + source
        preview = args.output / "previews" / source
        preview.parent.mkdir(parents=True, exist_ok=True)
        preview.write_text(current)
        links += check_markdown_links(source, current)
        updates.append({"path": source, "before": binding(ROOT / source),
                        "preview": str(preview.relative_to(ROOT)),
                        "currentSha256": hashlib.sha256(current.encode()).hexdigest(),
                        "historicalBodySha256": hashlib.sha256(history.encode()).hexdigest(),
                        "historicalBodyExact": True,
                        "diff": "".join(difflib.unified_diff(old.splitlines(keepends=True), current.splitlines(keepends=True), fromfile=row["snapshot"], tofile=source))})
    assert all(row["exists"] for row in links), [row for row in links if not row["exists"]]
    if basis:
        assert read_json(ROOT / GATE_PATH) == facts["finalGate"], "Reviewed correction cannot silently change gate"
    else:
        assert (ROOT / GATE_PATH).read_bytes() == (ROOT / originals[GATE_PATH]["snapshot"]).read_bytes()
    gate_preview = args.output / "previews" / GATE_PATH
    gate_preview.parent.mkdir(parents=True, exist_ok=True)
    gate_preview.write_text(json.dumps(facts["finalGate"], indent=2, ensure_ascii=False) + "\n")
    if args.apply:
        for item in updates:
            (ROOT / item["path"]).write_bytes((ROOT / item["preview"]).read_bytes())
        (ROOT / GATE_PATH).write_bytes(gate_preview.read_bytes())
    report = {"schema": "archcanvas-caption-route-entry-update/1",
              "createdUtc": datetime.now(timezone.utc).isoformat(),
              "status": "applied" if args.apply else "preview_only",
              "facts": binding(args.facts), "archive": binding(ROOT / ARCHIVE_PATH),
              "updatedEntries": updates, "markdownLinks": links,
              "gatePreview": str(gate_preview.relative_to(ROOT)),
              "currentHeaders": len(updates),
              "historicalBodiesPreserved": all(item["historicalBodyExact"] for item in updates)}
    (args.output / "report.json").write_text(json.dumps(report, indent=2, ensure_ascii=False) + "\n")
    print(json.dumps({"status": report["status"], "currentHeaders": len(updates),
                      "links": len(links), "report": str((args.output / "report.json").relative_to(ROOT))}, indent=2))


if __name__ == "__main__":
    main()
