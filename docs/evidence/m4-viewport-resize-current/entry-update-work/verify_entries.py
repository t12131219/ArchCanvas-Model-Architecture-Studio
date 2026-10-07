"""Independent viewport-stage document/history/byte/link readback.

Imports neither the updater/facts assembler nor product implementation. Its
relations certify documentation and frozen bytes, not browser/user acceptance.
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
PREFIX = "docs/evidence/m4-viewport-resize-current"
ARCHIVE = PREFIX + "/entry-update-work/before-entry-manifest.json"
GATE = "docs/evidence/m4-current-gate-audit.json"
STAGE = "docs/m4-viewport-resize.md"
INDEX = PREFIX + "/README.md"


def load(path):
    return json.loads((ROOT / path).read_bytes())


def bind(path):
    raw = (ROOT / path).read_bytes()
    return {"path": path, "bytes": len(raw), "sha256": hashlib.sha256(raw).hexdigest()}


def main():
    parser = ArgumentParser(description=__doc__)
    parser.add_argument("--facts", required=True)
    parser.add_argument("--update-report", required=True)
    parser.add_argument("--output", required=True)
    args = parser.parse_args()
    output = ROOT / args.output
    assert not output.exists(), "Retain all attempts"
    facts, update, archive = load(args.facts), load(args.update_report), load(ARCHIVE)
    frozen = {row["path"]: row for row in archive["inputs"]}
    checks, links = [], []

    def check(name, predicate):
        checks.append({"name": name, "passed": bool(predicate)})

    check("final facts and applied update", facts["status"] == "final_facts_ready" and update["status"] == "applied")
    check("seventeen original entry archive inputs", len(frozen) == len(archive["inputs"]) == 17)
    for row in archive["inputs"]:
        now = bind(row["snapshot"])
        check("archive bytes " + row["path"], now["bytes"] == row["bytes"] and now["sha256"] == row["sha256"])
    check("thirteen current headers", len(update["entries"]) == 13)
    current_paths, common = [], {"cn": [], "en": []}
    for row in update["entries"]:
        source = row["path"]
        current_paths.append(source)
        current = (ROOT / source).read_text()
        original = (ROOT / frozen[source]["snapshot"]).read_text()
        sections = list(re.finditer(r"^## ", current, re.M))
        old_sections = list(re.finditer(r"^## ", original, re.M))
        check("current/original sections " + source, len(sections) >= 2 and len(old_sections) >= 2)
        header = current[sections[0].start():sections[1].start()]
        history = current[sections[1].start():]
        check("whole historical body exact " + source, history == original[old_sections[1].start():])
        check("history digest exact " + source, hashlib.sha256(history.encode()).hexdigest() == row["historicalBodySha256"])
        check("preamble exact " + source, current[:sections[0].start()] == original[:old_sections[0].start()])
        preview = ROOT / args.update_report
        preview = preview.parent / "previews" / source
        check("preview applied bytes exact " + source, (ROOT / source).read_bytes() == preview.read_bytes())
        language = "en" if source.startswith("skills/") else "cn"
        required = ["partial", "not_started", "humans 0", "AI is not a human participant", "not presented FPS", "no generated model was executed"] if language == "en" else ["partial", "not_started", "真人 0", "AI 不计真人", "不是实际呈现 FPS", "未执行生成模型"]
        check("acceptance boundaries " + source, all(token in header for token in required))
        check("final version/counts " + source, all(token in header for token in ["index-_KAUBMcR.js", "index--unhoRTb.css", "430/430", "11/11", "115", "308/308"]))
        normalized = re.sub(r"(!?\[[^\]]*\])\([^\)]+\)", r"\1", header).split("Use this reference for figure creation")[0].rstrip()
        common[language].append(normalized)
    check("ten Chinese and three English matching current headers", len(common["cn"]) == 10 and len(common["en"]) == 3 and len(set(common["cn"])) == len(set(common["en"])) == 1)
    gate = load(GATE)
    old = load(frozen[GATE]["snapshot"])
    check("gate exact assembled final facts", gate == facts["finalGate"])
    check("full historical caption stability gate exact", gate["historicalCaptionStabilityGate"] == old)
    check("M4 partial M5 unstarted human0", gate["overall"] == "partial" and gate["m5"] == "not_started" and gate["humanParticipants"] == 0)
    reqs = {row["id"]: row for row in gate["requirements"]}
    oldreqs = {row["id"]: row for row in old["requirements"]}
    for key in ["base-models", "semantic-holdout", "shared-repeat-opaque"]:
        check("static source gate exact " + key, reqs[key] == oldreqs[key])
    check("research publication performance gates remain open", reqs["research-task"]["status"] == reqs["publication-review"]["status"] == "not_done" and reqs["browser-performance"]["status"] == "failed_or_unverified")
    check("historical three AI roles exact", gate["aiSimulatedRoles"] == old["aiSimulatedRoles"])
    check("historical caption build exact", gate["historicalCaptionStabilityBuild"] == old["build"])
    receipt = load(facts["buildReceipt"])
    check("current source/build/publication counts", len(receipt["inputs"]) == 112 and len(receipt["build"]) == 3 and len(receipt["publicationInputs"]) == 11)
    check("unified checks exit0 and inputs stable", all(row["exitCode"] == 0 for row in receipt["checks"]) and receipt["inputsUnchanged"] and receipt["publicationInputsUnchanged"])
    for row in receipt["inputs"] + receipt["build"] + receipt["publicationInputs"]:
        check("current checked bytes " + row["path"], bind(row["path"]) == {k: row[k] for k in ["path", "bytes", "sha256"]})
    for row in facts["evidenceBindings"]:
        check("final reviewed evidence bytes " + row["path"], bind(row["path"]) == row)
    package = gate["currentResearchPackage"]
    check("new package zero assignment collection human", package["assigned"] == package["collected"] == package["humans"] == 0 and not package["servicesStarted"] and not package["portsAvailabilityChecked"])
    check("new package manifest exact", bind(package["path"] + "/manifest.json")["sha256"] == package["manifestSha256"])
    trial = load(package["path"] + "/manifest.json")
    check("five pristine actual seats registered ports", len(trial["slots"]) == 5 and [row["port"] for row in trial["slots"]] == list(range(43621, 43626)) and all(row["participantCode"] is None and row["assignment"] == "unassigned" for row in trial["slots"]))
    stale = load(PREFIX + "/research-final-preparation/prior-package-verify.process.json")
    check("prior caption package official stale refusal retained", stale["exitCode"] == 1 and "Formal implementation changed after preparation; prepare a fresh package." in (ROOT / (PREFIX + "/research-final-preparation/prior-package-verify.stderr.txt")).read_text())
    for source in [STAGE, INDEX]:
        check("new stage index applied preview exact " + source, (ROOT / source).read_bytes() == (ROOT / args.update_report).parent.joinpath("previews", source).read_bytes())
    for source in ["skills/archcanvas/SKILL.md", "docs/m4-caption-stability-camera.md", "docs/evidence/m4-caption-stability-current/README.md"]:
        check("unchanged skill or prior stage exact " + source, bind(source)["bytes"] == frozen[source]["bytes"] and bind(source)["sha256"] == frozen[source]["sha256"])
    for source in current_paths + [STAGE, INDEX]:
        for value in re.findall(r"!?\[[^\]]*\]\(([^\)]+)\)", (ROOT / source).read_text()):
            target = value.strip().removeprefix("<").removesuffix(">")
            if re.match(r"(?:[a-zA-Z][a-zA-Z0-9+.-]*:|#)", target):
                continue
            resolved = ((ROOT / source).parent / unquote(target.split("#")[0].split("?")[0])).resolve()
            links.append({"source": source, "target": value, "exists": resolved.exists()})
    check("all current markdown links resolve", all(row["exists"] for row in links))
    gate_links = [{"path": path, "exists": (ROOT / path).is_file()} for row in gate["requirements"] for path in row["evidence"]]
    check("all gate evidence links resolve", all(row["exists"] for row in gate_links))
    report = {"schema": "archcanvas-viewport-entry-readback/1", "createdUtc": datetime.now(timezone.utc).isoformat(),
              "passed": sum(row["passed"] for row in checks), "total": len(checks), "checks": checks,
              "markdownLinks": links, "gateLinks": gate_links,
              "currentInputs": [bind(path) for path in current_paths + [STAGE, INDEX, GATE]],
              "scope": "Independent documentation/file/history/link relationships only; not product tests, browser pixels, user tasks, publication quality or presented performance acceptance."}
    output.write_text(json.dumps(report, ensure_ascii=False, indent=2) + "\n")
    print(json.dumps({"passed": report["passed"], "total": report["total"], "markdownLinks": len(links), "gateLinks": len(gate_links)}))
    raise SystemExit(0 if report["passed"] == report["total"] else 1)


if __name__ == "__main__":
    main()
