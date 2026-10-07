"""Preview current-only documentation updates; apply only final source-bound facts.

No product imports, runtime/browser operations, research preparation or old
evidence writes. Each invocation requires a new output directory.
"""
from argparse import ArgumentParser
from datetime import datetime, timezone
import difflib
import hashlib
import json
import os
from pathlib import Path
import re
from urllib.parse import unquote

HERE = Path(__file__).resolve().parent
ROOT = HERE.parents[3]
ARCHIVE = "docs/evidence/m4-caption-stability-current/before-change/manifest.json"
STAGE = "docs/m4-caption-stability-camera.md"
INDEX = "docs/evidence/m4-caption-stability-current/README.md"
GATE = "docs/evidence/m4-current-gate-audit.json"
ENTRIES = [
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


def read(path):
    return json.loads((ROOT / path).read_bytes())


def bind(path):
    p = ROOT / path
    raw = p.read_bytes()
    return {"path": path, "bytes": len(raw), "sha256": hashlib.sha256(raw).hexdigest()}


def split(text):
    parts = list(re.finditer(r"^## ", text, re.M))
    assert len(parts) >= 2, "Missing original current/historical sections"
    return text[:parts[0].start()], text[parts[1].start():]


def render(template, source, targets):
    for key, target in targets.items():
        template = template.replace("{{" + key + "}}", os.path.relpath(ROOT / target, (ROOT / source).parent))
    assert "{{" not in template and "}}" not in template, source
    return template.rstrip() + "\n\n"


def links(source, text, planned):
    rows = []
    for target in re.findall(r"!?\[[^\]]*\]\(([^\)]+)\)", text):
        value = target.strip().removeprefix("<").removesuffix(">")
        if re.match(r"(?:[a-zA-Z][a-zA-Z0-9+.-]*:|#)", value):
            continue
        resolved = ((ROOT / source).parent / unquote(value.split("#")[0].split("?")[0])).resolve()
        rows.append({"from": source, "target": target, "resolved": str(resolved),
                     "existsOrPlanned": resolved.exists() or resolved in planned})
    return rows


def validate_final(facts, old_gate):
    assert facts["status"] == "final_facts_ready"
    gate = facts["finalGate"]
    assert gate["overall"] == "partial" and gate["m5"] == "not_started" and gate["humanParticipants"] == 0
    assert gate["currentStage"] == STAGE and gate["currentEntryPreChangeArchive"] == ARCHIVE
    assert gate["aiSimulatedRoles"] == old_gate["aiSimulatedRoles"], "Auditors cannot become simulated/human participants"
    reqs = {row["id"]: row for row in gate["requirements"]}
    olds = {row["id"]: row for row in old_gate["requirements"]}
    assert set(reqs) == set(olds)
    for key in ("base-models", "semantic-holdout", "shared-repeat-opaque"):
        assert reqs[key] == olds[key], key
    assert reqs["research-task"]["status"] == reqs["publication-review"]["status"] == "not_done"
    assert reqs["browser-performance"]["status"] == "failed_or_unverified"
    assert gate["historicalCaptionRouteBuild"] == old_gate["build"]
    assert reqs["visual-authoring"]["observedHistoricalCaptionRoute"] == olds["visual-authoring"]["observedCurrentCaptionRoute"]
    assert reqs["publication-review"]["observedHistoricalCaptionRouteExportPreflight"] == olds["publication-review"]["observedCurrentExportPreflight"]
    receipt = read(facts["buildReceipt"])
    assert receipt["inputsUnchanged"] is True and receipt["publicationInputsUnchanged"] is True
    assert all(row["exitCode"] == 0 for row in receipt["checks"])
    for row in receipt["inputs"] + receipt["build"] + receipt["publicationInputs"]:
        assert bind(row["path"]) == {k: row[k] for k in ("path", "bytes", "sha256")}, row["path"]
    build = gate["build"]
    assert build["checks"] == facts["buildReceipt"]
    assert build["sourceTestConfigBindings"] == len(receipt["inputs"])
    assert build["distBindings"] == len(receipt["build"])
    assert build["totalSourceBuildBindings"] == len(receipt["inputs"]) + len(receipt["build"])
    assert build["publicationInputBindings"] == len(receipt["publicationInputs"])
    assert build["strictBuildExitCode"] == build["skipped"] == build["publicationSkipped"] == 0
    commands = {row["label"]: row for row in receipt["checks"]}
    suite = {name: int(value) for name, value in re.findall(r"^ℹ (tests|pass|fail|cancelled|skipped|todo) (\d+)$", (ROOT / commands["studio"]["log"]).read_text(), re.M)}
    assert suite["tests"] == suite["pass"] == build["studioTests"]
    assert suite["fail"] == suite["cancelled"] == suite["skipped"] == suite["todo"] == 0
    pub = (ROOT / commands["publication"]["log"]).read_text()
    count = re.findall(r"^Ran (\d+) tests? in ", pub, re.M)
    assert len(count) == 1 and int(count[0]) == build["publicationTests"] and pub.rstrip().endswith("OK")
    assets = [Path(row["path"]).name for row in receipt["build"]]
    assert build["js"] in assets and build["css"] in assets
    for row in facts["evidenceBindings"]:
        assert bind(row["path"]) == row, "Evidence changed: " + row["path"]
    package = gate["currentResearchPackage"]
    assert package["humans"] == package["assigned"] == package["collected"] == 0
    assert not package["servicesStarted"] and not package["portsAvailabilityChecked"]
    assert package["currentVerification"] == "prepared_and_verified"
    assert bind(package["path"] + "/manifest.json")["sha256"] == package["manifestSha256"]
    trial = read(package["path"] + "/manifest.json")
    assert len(trial["slots"]) == package["pristineSlots"] == 5
    assert all(row["participantCode"] is None and row["assignment"] == "unassigned" for row in trial["slots"])
    assert [row["port"] for row in trial["slots"]] == package["registeredPorts"]
    assert package["independentReadiness"]["passed"] == package["independentReadiness"]["total"]
    for req in gate["requirements"]:
        for path in req["evidence"]:
            assert path in (STAGE, INDEX) or (ROOT / path).is_file(), path


def main():
    parser = ArgumentParser(description=__doc__)
    parser.add_argument("facts", type=Path)
    parser.add_argument("--output", type=Path, required=True)
    parser.add_argument("--apply", action="store_true")
    args = parser.parse_args()
    facts_path = args.facts.resolve()
    facts = json.loads(facts_path.read_bytes())
    output = args.output.resolve()
    assert not output.exists(), "Retain prior attempts"
    assert ROOT in output.parents, "Evidence output must stay in formal workspace"
    archive = read(ARCHIVE)
    originals = {row["path"]: row for row in archive["inputs"]}
    assert len(originals) == 138
    for row in archive["inputs"]:
        actual = bind(row["snapshot"])
        assert actual["bytes"] == row["bytes"] and actual["sha256"] == row["sha256"], row["path"]
    old_gate = read(originals[GATE]["snapshot"])
    if facts["status"] == "final_facts_ready":
        validate_final(facts, old_gate)
    else:
        assert not args.apply, "Draft facts only create previews"
    targets = {"stage": STAGE, "index": INDEX, "gate": GATE, "archive": ARCHIVE, **facts.get("targets", {})}
    new_markdown = facts.get("newMarkdown", {})
    assert set(new_markdown).issubset({STAGE, INDEX})
    planned = {ROOT / path for path in [STAGE, INDEX, GATE]}
    output.mkdir(parents=True)
    entries, link_rows = [], []
    for source in ENTRIES:
        original = ROOT / originals[source]["snapshot"]
        assert (ROOT / source).read_bytes() == original.read_bytes(), "Uncoordinated current entry: " + source
        preamble, historical = split(original.read_text())
        header = render(facts["headers"]["en" if source.startswith("skills/") else "cn"], source, targets)
        assert len(re.findall(r"^## ", header, re.M)) == 1
        boundary = ["partial", "not_started", "humans 0", "AI is not a human participant", "not presented FPS", "no generated model was executed"] if source.startswith("skills/") else ["partial", "not_started", "真人 0", "AI 不计真人", "不是实际呈现 FPS", "未执行生成模型"]
        assert all(value in header for value in boundary), source
        if source == "skills/archcanvas/references/visual-workflow.md":
            header += VISUAL_INTRO + "\n\n"
        if source == "docs/m4-research-protocol.md" and facts.get("researchCommandSection"):
            header += render(facts["researchCommandSection"], source, targets)
        updated = preamble + header + historical
        assert split(updated)[1] == historical
        preview = output / "previews" / source
        preview.parent.mkdir(parents=True, exist_ok=True)
        preview.write_text(updated)
        entries.append({"path": source, "before": bind(source), "preview": str(preview.relative_to(ROOT)),
                        "currentSha256": hashlib.sha256(updated.encode()).hexdigest(),
                        "historicalBodySha256": hashlib.sha256(historical.encode()).hexdigest(),
                        "historicalBodyExact": True,
                        "diff": "".join(difflib.unified_diff(original.read_text().splitlines(keepends=True), updated.splitlines(keepends=True), fromfile=originals[source]["snapshot"], tofile=source))})
        link_rows += links(source, updated, planned)
    assert (ROOT / GATE).read_bytes() == (ROOT / originals[GATE]["snapshot"]).read_bytes()
    gate_preview = output / "previews" / GATE
    gate_preview.parent.mkdir(parents=True, exist_ok=True)
    gate_preview.write_text(json.dumps(facts["finalGate"], ensure_ascii=False, indent=2) + "\n")
    additions = []
    for target, text in new_markdown.items():
        assert not (ROOT / target).exists(), "Do not overwrite previous stage doc"
        preview = output / "previews" / target
        preview.parent.mkdir(parents=True, exist_ok=True)
        preview.write_text(text.rstrip() + "\n")
        additions.append({"path": target, "preview": str(preview.relative_to(ROOT)), "sha256": hashlib.sha256(preview.read_bytes()).hexdigest()})
        link_rows += links(target, preview.read_text(), planned)
    assert all(row["existsOrPlanned"] for row in link_rows), [row for row in link_rows if not row["existsOrPlanned"]]
    if args.apply:
        assert set(new_markdown) == {STAGE, INDEX}
        for row in additions + entries:
            (ROOT / row["path"]).write_bytes((ROOT / row["preview"]).read_bytes())
        (ROOT / GATE).write_bytes(gate_preview.read_bytes())
    report = {"schema": "archcanvas-caption-stability-entry-update/1", "createdUtc": datetime.now(timezone.utc).isoformat(),
              "status": "applied" if args.apply else "preview_only", "factsStatus": facts["status"],
              "facts": bind(str(facts_path.relative_to(ROOT))), "archive": bind(ARCHIVE),
              "updatedEntries": entries, "newMarkdown": additions, "gatePreview": str(gate_preview.relative_to(ROOT)),
              "currentHeaders": len(entries), "historicalBodiesPreserved": all(row["historicalBodyExact"] for row in entries),
              "markdownLinks": link_rows}
    (output / "report.json").write_text(json.dumps(report, ensure_ascii=False, indent=2) + "\n")
    print(json.dumps({"status": report["status"], "currentHeaders": len(entries), "newMarkdown": len(additions), "links": len(link_rows), "report": str((output / "report.json").relative_to(ROOT))}))


if __name__ == "__main__":
    main()
