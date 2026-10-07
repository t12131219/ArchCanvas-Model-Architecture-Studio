"""Preview/apply only source-bound memory-continuity-stage current documentation headers."""
from argparse import ArgumentParser
from pathlib import Path
from datetime import datetime, timezone
import hashlib
import json
import os
import re
from urllib.parse import unquote

HERE = Path(__file__).resolve().parent
ROOT = HERE.parents[3]
ARCHIVE = "docs/evidence/m4-memory-continuity-current/entry-update-work/before-entry-manifest.json"
STAGE = "docs/m4-memory-continuity.md"
INDEX = "docs/evidence/m4-memory-continuity-current/README.md"
GATE = "docs/evidence/m4-current-gate-audit.json"
ENTRIES = ["README.md", "docs/acceptance.md", "docs/capability-matrix.md", "docs/evidence/README.md",
           "docs/m4-ai-usability-audit.md", "docs/m4-completion.md", "docs/m4-exit-audit.md",
           "docs/m4-human-review-handoff.md", "docs/m4-performance.md", "docs/m4-research-protocol.md",
           "skills/archcanvas/references/formal-alpha.md", "skills/archcanvas/references/runtime-compatibility.md",
           "skills/archcanvas/references/visual-workflow.md"]


def bind(path):
    raw = (ROOT / path).read_bytes()
    return {"path": path, "bytes": len(raw), "sha256": hashlib.sha256(raw).hexdigest()}


def load(path):
    return json.loads((ROOT / path).read_text())


def split(text):
    parts = list(re.finditer(r"^## ", text, re.M))
    assert len(parts) >= 2
    return text[:parts[0].start()], text[parts[1].start():]


def render(template, source, targets):
    for key, target in targets.items():
        template = template.replace("{{" + key + "}}", os.path.relpath(ROOT / target, (ROOT / source).parent))
    assert "{{" not in template and "}}" not in template
    return template.rstrip() + "\n\n"


def validate_final(facts, old_gate):
    gate = facts["finalGate"]
    assert facts["status"] == "final_facts_ready"
    assert gate["overall"] == "partial" and gate["m5"] == "not_started" and gate["humanParticipants"] == 0
    assert gate["currentStage"] == STAGE and gate["aiSimulatedRoles"] == old_gate["aiSimulatedRoles"]
    assert gate["historicalViewportResizeGateArchive"] == bind("docs/evidence/m4-memory-continuity-current/entry-update-work/before-entry-inputs/docs/evidence/m4-current-gate-audit.json"), "Retain prior frozen gate archive binding"
    reqs = {r["id"]: r for r in gate["requirements"]}
    oldreqs = {r["id"]: r for r in old_gate["requirements"]}
    assert set(reqs) == set(oldreqs)
    for key in ("base-models", "semantic-holdout", "shared-repeat-opaque"):
        assert reqs[key] == oldreqs[key]
    assert reqs["research-task"]["status"] == reqs["publication-review"]["status"] == "not_done"
    assert reqs["browser-performance"]["status"] == "failed_or_unverified"
    receipt = load(facts["buildReceipt"])
    assert receipt["inputsUnchanged"] and receipt["publicationInputsUnchanged"]
    assert all(r["exitCode"] == 0 for r in receipt["checks"])
    for row in receipt["inputs"] + receipt["build"] + receipt["publicationInputs"]:
        assert bind(row["path"]) == {k: row[k] for k in ("path", "bytes", "sha256")}, row["path"]
    assert gate["build"]["checks"] == facts["buildReceipt"]
    assert gate["build"]["sourceTestConfigBindings"] == len(receipt["inputs"])
    assert gate["build"]["distBindings"] == len(receipt["build"])
    assert gate["build"]["publicationInputBindings"] == len(receipt["publicationInputs"])
    for row in facts["evidenceBindings"]:
        assert bind(row["path"]) == row
    package = gate["currentResearchPackage"]
    assert package["humans"] == package["assigned"] == package["collected"] == 0
    assert not package["servicesStarted"] and not package["portsAvailabilityChecked"]
    assert package["currentVerification"] == "prepared_and_verified"
    assert bind(package["path"] + "/manifest.json")["sha256"] == package["manifestSha256"]
    slots = load(package["path"] + "/manifest.json")["slots"]
    assert len(slots) == 5 and [r["port"] for r in slots] == list(range(43631, 43636))
    assert all(r["participantCode"] is None and r["assignment"] == "unassigned" for r in slots)


def main():
    parser = ArgumentParser(description=__doc__)
    parser.add_argument("facts")
    parser.add_argument("--output", required=True)
    parser.add_argument("--apply", action="store_true")
    args = parser.parse_args()
    facts = load(args.facts)
    archive = load(ARCHIVE)
    frozen = {r["path"]: r for r in archive["inputs"]}
    assert len(frozen) == 17
    for row in frozen.values():
        actual = bind(row["snapshot"])
        assert actual["bytes"] == row["bytes"] and actual["sha256"] == row["sha256"]
        assert (ROOT / row["path"]).read_bytes() == (ROOT / row["snapshot"]).read_bytes(), row["path"]
    old_gate = load(frozen[GATE]["snapshot"])
    if facts["status"] == "final_facts_ready":
        validate_final(facts, old_gate)
    else:
        assert not args.apply
    output = ROOT / args.output
    assert ROOT in output.parents and not output.exists(), "Retain all attempts"
    targets = {"stage": STAGE, "index": INDEX, "gate": GATE, "archive": ARCHIVE, **facts.get("targets", {})}
    contents = {}
    entry_rows = []
    for source in ENTRIES:
        original = (ROOT / source).read_text()
        preamble, history = split(original)
        language = "en" if source.startswith("skills/") else "cn"
        header = render(facts["headers"][language], source, targets)
        assert len(re.findall(r"^## ", header, re.M)) == 1
        required = ["partial", "not_started", "humans 0", "AI is not a human participant", "not presented FPS", "no generated model was executed"] if language == "en" else ["partial", "not_started", "真人 0", "AI 不计真人", "不是实际呈现 FPS", "未执行生成模型"]
        assert all(s in header for s in required)
        if source.endswith("visual-workflow.md"):
            header += "Use this reference for figure creation, visual refinement, expansion, and export. These are acceptance contracts for a compatible Studio, not assertions that every installed runtime supports them. Check operations before invoking them.\n\n"
        contents[source] = preamble + header + history
        assert split(contents[source])[1] == history
        entry_rows.append({"path": source, "before": bind(source), "historicalBodySha256": hashlib.sha256(history.encode()).hexdigest(), "historicalBodyExact": True})
    assert set(facts["newMarkdown"]) == {STAGE, INDEX}
    for source, content in facts["newMarkdown"].items():
        assert not (ROOT / source).exists()
        contents[source] = content.rstrip() + "\n"
    planned = {ROOT / p for p in contents}
    links = []
    for source, content in contents.items():
        for target in re.findall(r"!?\[[^\]]*\]\(([^\)]+)\)", content):
            value = target.strip().removeprefix("<").removesuffix(">")
            if re.match(r"(?:[a-zA-Z][a-zA-Z0-9+.-]*:|#)", value):
                continue
            path = ((ROOT / source).parent / unquote(value.split("#")[0].split("?")[0])).resolve()
            links.append({"source": source, "target": target, "existsOrPlanned": path.exists() or path in planned})
    assert all(r["existsOrPlanned"] for r in links)
    output.mkdir(parents=True)
    for source, content in contents.items():
        preview = output / "previews" / source
        preview.parent.mkdir(parents=True, exist_ok=True)
        preview.write_text(content)
        if args.apply:
            (ROOT / source).write_bytes(preview.read_bytes())
    gate_preview = output / "previews" / GATE
    gate_preview.parent.mkdir(parents=True, exist_ok=True)
    gate_preview.write_text(json.dumps(facts["finalGate"], ensure_ascii=False, indent=2) + "\n")
    if args.apply:
        (ROOT / GATE).write_bytes(gate_preview.read_bytes())
    report = {"schema": "archcanvas-memory-continuity-entry-update/1", "createdUtc": datetime.now(timezone.utc).isoformat(), "status": "applied" if args.apply else "preview_only", "factsStatus": facts["status"], "facts": bind(args.facts), "archive": bind(ARCHIVE), "entries": entry_rows, "contentPaths": list(contents), "markdownLinks": links, "gatePreview": str(gate_preview.relative_to(ROOT))}
    (output / "report.json").write_text(json.dumps(report, ensure_ascii=False, indent=2) + "\n")
    print(json.dumps({"status": report["status"], "headers": len(entry_rows), "newMarkdown": 2, "links": len(links)}))


if __name__ == "__main__":
    main()
