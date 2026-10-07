"""Independent readback of current documentation and frozen byte relationships.

Does not import the entry updater or any product implementation.
"""
from argparse import ArgumentParser
from datetime import datetime, timezone
import hashlib
import json
from pathlib import Path
import re
from urllib.parse import unquote

HERE = Path(__file__).resolve().parent
ROOT = HERE.parents[3]
ARCHIVE = "docs/evidence/m4-caption-stability-current/before-change/manifest.json"
GATE = "docs/evidence/m4-current-gate-audit.json"
STAGE = "docs/m4-caption-stability-camera.md"
INDEX = "docs/evidence/m4-caption-stability-current/README.md"


def load(path):
    return json.loads((ROOT / path).read_bytes())


def binding(path):
    raw = (ROOT / path).read_bytes()
    return {"path": path, "bytes": len(raw), "sha256": hashlib.sha256(raw).hexdigest()}


def main():
    parser = ArgumentParser(description=__doc__)
    parser.add_argument("--facts", required=True)
    parser.add_argument("--update-report", required=True)
    parser.add_argument("--output", required=True)
    args = parser.parse_args()
    output = ROOT / args.output
    assert not output.exists(), "Retain earlier readbacks"
    facts, update, archive = load(args.facts), load(args.update_report), load(ARCHIVE)
    frozen = {item["path"]: item for item in archive["inputs"]}
    checks, markdown_links, inputs = [], [], []

    def check(name, predicate):
        checks.append({"name": name, "passed": bool(predicate)})

    check("final facts and applied review", facts["status"] == "final_facts_ready" and update["status"] == "applied")
    check("138 unique archived inputs", len(archive["inputs"]) == len(frozen) == 138)
    for item in archive["inputs"]:
        actual = binding(item["snapshot"])
        check("pre-change original exact " + item["path"], actual["bytes"] == item["bytes"] and actual["sha256"] == item["sha256"])
    check("13 current headers", len(update["updatedEntries"]) == 13)
    common = {"cn": [], "en": []}
    entry_paths = []
    for item in update["updatedEntries"]:
        path = item["path"]
        entry_paths.append(path)
        current = (ROOT / path).read_text()
        original = (ROOT / frozen[path]["snapshot"]).read_text()
        now_sections = list(re.finditer(r"^## ", current, re.M))
        old_sections = list(re.finditer(r"^## ", original, re.M))
        check("level-two sections " + path, len(now_sections) >= 2 and len(old_sections) >= 2)
        history = current[now_sections[1].start():]
        check("whole old historical body exact " + path, history == original[old_sections[1].start():])
        check("applied preview exact " + path, (ROOT / path).read_bytes() == (ROOT / item["preview"]).read_bytes())
        check("applied current digest exact " + path, binding(path)["sha256"] == item["currentSha256"])
        check("old body digest exact " + path, hashlib.sha256(history.encode()).hexdigest() == item["historicalBodySha256"])
        header = current[now_sections[0].start():now_sections[1].start()]
        language = "en" if path.startswith("skills/") else "cn"
        boundary = ["partial", "not_started", "humans 0", "AI is not a human participant", "not presented FPS", "no generated model was executed"] if language == "en" else ["partial", "not_started", "真人 0", "AI 不计真人", "不是实际呈现 FPS", "未执行生成模型"]
        check("acceptance boundaries " + path, all(token in header for token in boundary))
        build = facts["finalGate"]["build"]
        package = facts["finalGate"]["currentResearchPackage"]
        tokens = [build["js"], build["css"], f"{build['studioTests']}/{build['studioTests']}",
                  f"{build['publicationTests']}/{build['publicationTests']}", str(build["totalSourceBuildBindings"]),
                  f"{package['independentReadiness']['passed']}/{package['independentReadiness']['total']}"]
        check("bound final version/count scope " + path, all(token in header for token in tokens))
        normalized = re.sub(r"(!?\[[^\]]*\])\([^\)]+\)", r"\1", header)
        normalized = normalized.split("### 当前相机与标签包")[0].split("Use this reference for figure creation")[0].rstrip()
        common[language].append(normalized)
        inputs.append(binding(path))
    check("10 Chinese and3 English common current headers", len(common["cn"]) == 10 and len(common["en"]) == 3 and len(set(common["cn"])) == len(set(common["en"])) == 1)
    gate = load(GATE)
    check("gate exact final facts", gate == facts["finalGate"])
    check("partial M4 and unstarted M5 human0", gate["overall"] == "partial" and gate["m5"] == "not_started" and gate["humanParticipants"] == 0)
    reqs = {row["id"]: row for row in gate["requirements"]}
    check("real-human publication and performance remain open", reqs["research-task"]["status"] == reqs["publication-review"]["status"] == "not_done" and reqs["browser-performance"]["status"] == "failed_or_unverified")
    old_gate = load(frozen[GATE]["snapshot"])
    old_reqs = {row["id"]: row for row in old_gate["requirements"]}
    for name in ("base-models", "semantic-holdout", "shared-repeat-opaque"):
        check("old source gate exact " + name, reqs[name] == old_reqs[name])
    check("historical three AI role evidence exact", gate["aiSimulatedRoles"] == old_gate["aiSimulatedRoles"])
    check("historical Divs build exact", gate["historicalCaptionRouteBuild"] == old_gate["build"])
    check("historical caption observation exact", reqs["visual-authoring"]["observedHistoricalCaptionRoute"] == old_reqs["visual-authoring"]["observedCurrentCaptionRoute"])
    check("historical export preflight exact", reqs["publication-review"]["observedHistoricalCaptionRouteExportPreflight"] == old_reqs["publication-review"]["observedCurrentExportPreflight"])
    receipt = load(facts["buildReceipt"])
    check("unified source inputs remained unchanged", receipt["inputsUnchanged"] is True and receipt["publicationInputsUnchanged"] is True)
    check("all unified commands exit0", all(row["exitCode"] == 0 for row in receipt["checks"]))
    for row in receipt["inputs"] + receipt["build"] + receipt["publicationInputs"]:
        check("current source/build/publication exact " + row["path"], binding(row["path"]) == {k: row[k] for k in ("path", "bytes", "sha256")})
    for row in facts["evidenceBindings"]:
        check("reviewed evidence exact " + row["path"], binding(row["path"]) == row)
    package = gate["currentResearchPackage"]
    check("zero assigned collected human records", package["humans"] == package["assigned"] == package["collected"] == 0)
    check("readiness is bounded complete relationship set", package["independentReadiness"]["passed"] == package["independentReadiness"]["total"])
    check("research manifest exact", binding(package["path"] + "/manifest.json")["sha256"] == package["manifestSha256"])
    trial = load(package["path"] + "/manifest.json")
    check("five actual unused seats", len(trial["slots"]) == 5 and all(row["participantCode"] is None and row["assignment"] == "unassigned" for row in trial["slots"]))
    check("registered ports from exact manifest", [row["port"] for row in trial["slots"]] == package["registeredPorts"])
    check("no seat service or port availability certificate", not package["servicesStarted"] and not package["portsAvailabilityChecked"])
    new_docs = {row["path"]: row for row in update["newMarkdown"]}
    check("exact two new stage/index paths", set(new_docs) == {STAGE, INDEX})
    for path, row in new_docs.items():
        check("new doc preview/source exact " + path, (ROOT / path).read_bytes() == (ROOT / row["preview"]).read_bytes() and binding(path)["sha256"] == row["sha256"])
    for path in entry_paths + [STAGE, INDEX]:
        text = (ROOT / path).read_text()
        for target in re.findall(r"!?\[[^\]]*\]\(([^\)]+)\)", text):
            cleaned = target.strip().removeprefix("<").removesuffix(">")
            if re.match(r"(?:[a-zA-Z][a-zA-Z0-9+.-]*:|#)", cleaned):
                continue
            resolved = ((ROOT / path).parent / unquote(cleaned.split("#")[0].split("?")[0])).resolve()
            markdown_links.append({"from": path, "target": target, "resolved": str(resolved), "exists": resolved.exists()})
    check("all current Markdown links resolve", all(row["exists"] for row in markdown_links))
    gate_links = [{"path": path, "exists": (ROOT / path).is_file()} for req in gate["requirements"] for path in req["evidence"]]
    check("all current gate paths resolve", all(row["exists"] for row in gate_links))
    for path in ("docs/m4-caption-association-shortcuts.md", "docs/m4-ai-usability-audit.md"):
        # The first is a frozen prior-stage doc; the second is a current entry
        # whose exact historical body was checked above.
        if path not in entry_paths:
            check("prior stage exact " + path, binding(path)["sha256"] == frozen[path]["sha256"])
    inputs += [binding(GATE), binding(STAGE), binding(INDEX)]
    result = {"schema": "archcanvas-caption-stability-entry-readback/1", "createdUtc": datetime.now(timezone.utc).isoformat(),
              "passed": sum(row["passed"] for row in checks), "total": len(checks), "checks": checks,
              "markdownLinks": markdown_links, "gateLinks": gate_links, "currentInputs": inputs,
              "scope": "Documentation/file/link relationships; not product tests, real-user tasks, physical publication or presented-performance acceptance."}
    output.write_text(json.dumps(result, ensure_ascii=False, indent=2) + "\n")
    print(json.dumps({"passed": result["passed"], "total": result["total"], "markdownLinks": len(markdown_links), "gateLinks": len(gate_links), "output": args.output}))
    raise SystemExit(0 if result["passed"] == result["total"] else 1)


if __name__ == "__main__":
    main()
