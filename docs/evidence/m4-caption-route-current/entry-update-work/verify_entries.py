"""Independent documentation readback; never imports runtime or updater helpers."""
from argparse import ArgumentParser
from datetime import datetime, timezone
import hashlib
import json
from pathlib import Path
import re
from urllib.parse import unquote

HERE = Path(__file__).resolve().parent
ROOT = HERE.parents[3]


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
    assert not output.exists(), "Never overwrite an earlier verification"
    facts = load(args.facts)
    update = load(args.update_report)
    archive = load("docs/evidence/m4-caption-route-current/before-change/manifest.json")
    old = {row["path"]: row for row in archive["inputs"]}
    checks, links, inputs = [], [], []

    def check(name, condition):
        checks.append({"name": name, "passed": bool(condition)})

    check("facts ready", facts["status"] == "final_facts_ready")
    check("13 applied current headers", update["status"] == "applied" and len(update["updatedEntries"]) == 13)
    for row in archive["inputs"]:
        actual = bind(row["snapshot"])
        check("126 original bytes " + row["path"], actual["bytes"] == row["bytes"] and actual["sha256"] == row["sha256"])
    common = {"cn": [], "en": []}
    paths = []
    expected_build = facts["finalGate"]["build"]
    expected_research = facts["finalGate"]["currentResearchPackage"]
    expected_readiness = expected_research["independentReadiness"]
    expected_ports = expected_research["registeredPorts"]
    port_range = f"{expected_ports[0]}–{expected_ports[-1]}"
    for row in update["updatedEntries"]:
        path = row["path"]
        paths.append(path)
        current = (ROOT / path).read_text()
        original = (ROOT / old[path]["snapshot"]).read_text()
        current_parts = list(re.finditer(r"^## ", current, re.M))
        old_parts = list(re.finditer(r"^## ", original, re.M))
        check("two sections " + path, len(current_parts) >= 2 and len(old_parts) >= 2)
        history = current[current_parts[1].start():]
        check("whole historical body exact " + path, history == original[old_parts[1].start():])
        check("preview bytes exact " + path, (ROOT / path).read_bytes() == (ROOT / row["preview"]).read_bytes())
        check("current header sha exact " + path, bind(path)["sha256"] == row["currentSha256"])
        header = current[current_parts[0].start():current_parts[1].start()]
        tokens = [expected_build["js"], expected_build["css"],
                  f"{expected_build['studioTests']}/{expected_build['studioTests']}",
                  f"{expected_build['publicationTests']}/{expected_build['publicationTests']}",
                  str(expected_build["totalSourceBuildBindings"]),
                  f"{expected_readiness['passed']}/{expected_readiness['total']}", port_range]
        check("current asset/test scope " + path, all(token in header for token in tokens))
        normalized = re.sub(r"(!?\[[^\]]*\])\([^\)]+\)", r"\1", header)
        # Extra read-only research opening and visual workflow contract are per-file.
        normalized = normalized.split("### 当前 Caption/route 包")[0].split("Use this reference for figure creation")[0].rstrip()
        language = "en" if path.startswith("skills/") else "cn"
        common[language].append(normalized)
        inputs.append(bind(path))
    check("ten Chinese and three English common headers", len(common["cn"]) == 10 and len(common["en"]) == 3 and len(set(common["cn"])) == len(set(common["en"])) == 1)
    gate = load("docs/evidence/m4-current-gate-audit.json")
    check("gate equals reviewed final facts", gate == facts["finalGate"])
    reqs = {row["id"]: row for row in gate["requirements"]}
    check("M4 partial M5 not started zero humans", gate["overall"] == "partial" and gate["m5"] == "not_started" and gate["humanParticipants"] == 0)
    check("open actual human/publication/performance", reqs["research-task"]["status"] == reqs["publication-review"]["status"] == "not_done" and reqs["browser-performance"]["status"] == "failed_or_unverified")
    old_gate = load(old["docs/evidence/m4-current-gate-audit.json"]["snapshot"])
    old_reqs = {row["id"]: row for row in old_gate["requirements"]}
    for name in ("base-models", "semantic-holdout", "shared-repeat-opaque"):
        check("old static gate exact " + name, reqs[name] == old_reqs[name])
    check("historical actual AI roles exact", gate["aiSimulatedRoles"] == old_gate["aiSimulatedRoles"])
    for name, new_name, req_name in [
        ("observedCurrentCaption", "observedHistoricalBtwCaption", "visual-authoring"),
        ("observedCurrentBtw7", "observedHistoricalBtw7", "browser-performance"),
        ("observedCurrentExportPreflight", "observedHistoricalBtwExportPreflight", "publication-review"),
    ]:
        check("historical BTw exact " + name, reqs[req_name][new_name] == old_reqs[req_name][name])
    receipt = load(gate["build"]["checks"])
    for row in receipt["inputs"] + receipt["build"] + receipt["publicationInputs"]:
        check("current product exact " + row["path"], bind(row["path"]) == {key: row[key] for key in ["path", "bytes", "sha256"]})
    ready = load(facts["researchReadiness"])
    current_research = gate["currentResearchPackage"]
    check("frozen readiness separate from humans", ready["currentBuild"]["independentReadiness"] == current_research["independentReadiness"] == expected_readiness and expected_readiness["passed"] == expected_readiness["total"])
    check("fresh research manifest exact", bind(current_research["path"] + "/manifest.json")["sha256"] == current_research["manifestSha256"])
    package = load(current_research["path"] + "/manifest.json")
    check("five unused seats", len(package["slots"]) == 5 and all(row["participantCode"] is None and row["assignment"] == "unassigned" for row in package["slots"]))
    check("registered ports actual", [row["port"] for row in package["slots"]] == current_research["registeredPorts"] == expected_ports)
    check("no services/port certification", not current_research["servicesStarted"] and not current_research["portsAvailabilityChecked"])
    paths += [gate["currentStage"], "docs/evidence/m4-caption-route-current/README.md"]
    for path in paths:
        text = (ROOT / path).read_text()
        for target in re.findall(r"!?\[[^\]]*\]\(([^\)]+)\)", text):
            target = target.strip().removeprefix("<").removesuffix(">")
            if re.match(r"(?:[a-zA-Z][a-zA-Z0-9+.-]*:|#)", target):
                continue
            resolved = ((ROOT / path).parent / unquote(target.split("#")[0].split("?")[0])).resolve()
            links.append({"from": path, "target": target, "resolved": str(resolved), "exists": resolved.exists()})
    check("all Markdown links resolve", all(row["exists"] for row in links))
    gate_links = [{"path": path, "exists": (ROOT / path).is_file()}
                  for req in gate["requirements"] for path in req["evidence"]]
    check("all gate links resolve", all(row["exists"] for row in gate_links))
    # Owned old-stage documents/evidence are not rewritten by entry updates.
    for path in ("docs/m4-ai-simulated-current.md", "docs/m4-draft-port-legibility.md",
                 "docs/m4-native-drain-caption.md", "docs/evidence/m4-ai-simulated-current/README.md",
                 "docs/evidence/m4-performance-next-current/README.md"):
        check("prior stage unchanged " + path, bind(path)["sha256"] == old[path]["sha256"])
    inputs += [bind("docs/evidence/m4-current-gate-audit.json"), bind(gate["currentStage"]),
               bind("docs/evidence/m4-caption-route-current/README.md")]
    result = {"schema": "archcanvas-caption-route-current-entry-readback/1",
              "createdUtc": datetime.now(timezone.utc).isoformat(),
              "passed": sum(row["passed"] for row in checks), "total": len(checks),
              "checks": checks, "markdownLinks": links, "gateLinks": gate_links,
              "currentInputs": inputs,
              "scope": "Documentation, bytes and link relationships only; not product tests, human tasks, physical review or presented performance certification."}
    output.write_text(json.dumps(result, indent=2, ensure_ascii=False) + "\n")
    print(json.dumps({"passed": result["passed"], "total": result["total"],
                      "markdownLinks": len(links), "gateLinks": len(gate_links),
                      "output": args.output}, indent=2))
    raise SystemExit(0 if result["passed"] == result["total"] else 1)


if __name__ == "__main__":
    main()
