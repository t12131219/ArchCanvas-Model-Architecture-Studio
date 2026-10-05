"""Independent, read-only review of frozen native observation audit 3.

No product/auditor import, model execution, browser interaction, or raw editing.
The existing independent geometry oracle is rerun; it is not a second oracle.
"""
import hashlib
import json
import math
import pathlib
import subprocess
import xml.etree.ElementTree as ET
from datetime import datetime, timezone

HERE = pathlib.Path(__file__).resolve().parent
NATIVE = HERE.parent
ROOT = NATIVE.parents[3]
AUDIT = NATIVE / "independent-observation-audit-3"
NS = "{http://www.w3.org/2000/svg}"


def read(path):
    return json.loads(path.read_text())


def digest(path):
    b = path.read_bytes()
    return {"path": str(path.resolve()), "bytes": len(b), "sha256": hashlib.sha256(b).hexdigest()}


def quantile95(values):
    return sorted(values)[math.ceil(len(values) * .95) - 1] if values else None


def norm_svg(g):
    svg = ET.fromstring(g["svgMarkup"])
    svg.attrib.pop("data-revision")
    meta = svg.find(NS + "metadata")
    facts = json.loads(meta.text)
    facts.pop("revision")
    meta.text = json.dumps(facts, ensure_ascii=False, separators=(",", ":"))
    return ET.tostring(svg, encoding="unicode")


def geometry_signature(g):
    return [g["revision"], g["camera"]["matrix"], [[key, o.get("canvas"), o.get("screen"), o.get("label")] if o else [key, None, None, None] for key, o in g["objects"].items()]]


findings = []
checks = []


def check(name, okay, evidence=None):
    checks.append({"check": name, "passed": bool(okay), "evidence": evidence})
    if not okay:
        findings.append({"title": name, "evidence": evidence})


manifest = read(AUDIT / "manifest.json")
bound_paths = [pathlib.Path(r["path"]) for r in manifest["inputs"] + manifest["outputs"]] + [AUDIT / "manifest.json"]
initial = [digest(path) for path in bound_paths]
for group in ("inputs", "outputs"):
    mismatch = [r for r in manifest[group] if r != digest(pathlib.Path(r["path"]))]
    check("manifest " + group + " exact bytes/hash", not mismatch, {"checked": len(manifest[group]), "mismatches": mismatch})
check("manifest output coverage", {r["path"] for r in manifest["outputs"]} == {str(p.resolve()) for p in AUDIT.iterdir() if p.is_file() and p.name != "manifest.json"})
summary = read(AUDIT / "audit-summary.json")
check("summary inputs equal manifest", summary["inputBindings"] == manifest["inputs"])

raw_path = NATIVE / "mlp-four-directions-1/raw-full.json"
raw = read(raw_path)
reassembly = read(AUDIT / "reassembly-audit.json")
index = read(NATIVE / "mlp-four-directions-1/raw-chunk-index.json")
chunks = []
offset = 0
chunk_consistent = True
for entry in index["chunks"]:
    path = NATIVE / "mlp-four-directions-1/raw-chunks" / pathlib.Path(entry["file"]).name
    chunk = path.read_text()
    chunk_consistent &= entry["offset"] == offset and entry["length"] == len(chunk)
    chunks.append(chunk)
    offset += len(chunk)
check("70 contiguous chunks reassemble byte exactly", len(chunks) == 70 and chunk_consistent and "".join(chunks).encode() == raw_path.read_bytes(), {"unicodeCharacters": offset, "utf8Bytes": raw_path.stat().st_size})
check("reassembly summary arithmetic", reassembly["unicodeCharacters"] == offset and reassembly["utf8Bytes"] == raw_path.stat().st_size and reassembly["full"] == digest(raw_path))
try:
    read(NATIVE / "mlp-four-directions-1/raw.json")
    truncated_invalid = False
except json.JSONDecodeError:
    truncated_invalid = True
check("original truncated JSON remains invalid", truncated_invalid)

# A pair table is built once, with both degree counts, including unassigned
# trusted inputs. This does not import the audited matching implementation.
eligible = [e for e in raw["events"] if e["trusted"] and e["type"] in {"pointerdown", "pointerup", "click", "keydown", "keyup"} and e["target"]["token"]]
pairs = [(event["id"], i) for event in eligible for i, entry in enumerate(raw["eventTiming"]) if entry["interactionId"] > 0 and entry["name"] == event["type"] and entry["targetToken"] == event["target"]["token"] and -8 <= event["eventAt"] - entry["startAt"] <= 8]
matches = []
interaction_max = {}
for event in eligible:
    if event["trialId"] is None:
        continue
    candidates = [j for eid, j in pairs if eid == event["id"]]
    j = candidates[0] if len(candidates) == 1 and sum(index == candidates[0] for _, index in pairs) == 1 else None
    entry = raw["eventTiming"][j] if j is not None else None
    matches.append({"inputId": event["id"], "nativeEntryIndex": j, "interactionId": entry["interactionId"] if entry else None, "nativeDurationMs": entry["durationMs"] if entry else None})
    if entry:
        key = str(entry["interactionId"])
        interaction_max[key] = max(interaction_max.get(key, 0), entry["durationMs"])
timing = read(AUDIT / "bilateral-event-timing-audit.json")
check("independent bilateral Event Timing matches", matches == timing["matches"], {"allCompetingInputs": len(eligible), "assigned": len(matches), "matched": sum(m["nativeEntryIndex"] is not None for m in matches)})
check("deduplicated interaction maxima and p95", interaction_max == timing["interactionMaxDurationsMs"] and quantile95(list(interaction_max.values())) == timing["matchedInteractionP95Ms"], {"interactions": len(interaction_max), "p95Ms": quantile95(list(interaction_max.values()))})

canonical_path = ROOT / "docs/evidence/browser-visual-matrix-bcf-full/captures/mlp-level1-paper-180/canvas.json"
canonical_doc = read(canonical_path)
canonical = canonical_doc.get("document", canonical_doc)["architecture"]
nodes = {n["id"]: n for n in canonical["nodes"]}
edges = {e["id"]: e for e in canonical["edges"]}
snapshots = {}
canonical_failures = []
for trial in raw["trials"]:
    for phase in ("before", "after"):
        g = trial[phase]
        svg = ET.fromstring(g["svgMarkup"])
        meta = json.loads(svg.find(NS + "metadata").text)
        label = trial["id"] + "-" + phase
        try:
            assert meta["documentId"] == g["documentId"] == svg.get("data-document-id")
            assert meta["revision"] == g["revision"] == int(svg.get("data-revision"))
            assert meta["sourceDigest"] == g["sourceDigest"] == canonical["sourceDigest"]
            assert meta["irDigest"] == g["irDigest"] == canonical["irDigest"]
            assert len(meta["sourceFacts"]) == len(nodes) and {f["id"] for f in meta["sourceFacts"]} == set(nodes)
            for fact in meta["sourceFacts"]:
                source = nodes[fact["id"]]
                assert fact["sourceLabel"] == source["label"]
                assert all(fact.get(k) == source.get(k) for k in ("kind", "category", "source", "evidence", "instanceId", "callId", "repeat", "outputPath"))
                if "callCount" in fact:
                    assert fact["callCount"] == sum(n.get("instanceId") == fact["instanceId"] for n in nodes.values())
            node_groups = [el for el in svg.iter() if el.get("data-node-id") and not el.get("data-port-id")]
            assert len(node_groups) == len(g["visibleIds"]) and {el.get("data-node-id") for el in node_groups} == set(g["visibleIds"])
            assert {n["sceneNodeId"] for n in meta["renderedNodes"]} == set(g["visibleIds"])
            assert all(el.get("data-canonical-id") == el.get("data-node-id") for el in node_groups)
            groups = {el.get("data-node-id"): el for el in node_groups}
            def owner(identity):
                visited = set()
                while identity not in groups:
                    assert identity not in visited
                    visited.add(identity)
                    identity = nodes[identity]["parentId"]
                return identity
            represented = set()
            for binding in meta["renderedBindings"]:
                assert binding["canonicalEdgeIds"] and not represented.intersection(binding["canonicalEdgeIds"])
                represented.update(binding["canonicalEdgeIds"])
                assert any(edges[e]["source"] == binding["source"] and edges[e]["target"] == binding["target"] for e in binding["canonicalEdgeIds"])
                for eid in binding["canonicalEdgeIds"]:
                    e = edges[eid]
                    assert e["tensorId"] == binding["tensorId"] and e["role"] == binding["role"]
                    for endpoint, direction in (("source", "out"), ("target", "in")):
                        assert owner(e[endpoint]["nodeId"]) == owner(binding[endpoint]["nodeId"])
                        assert any(p["id"] == e[endpoint]["portId"] and p["direction"] == direction for p in nodes[e[endpoint]["nodeId"]]["ports"])
            edge_groups = [el for el in svg.iter() if el.get("data-edge-id")]
            assert len(edge_groups) == len(meta["renderedBindings"]) and {el.get("data-edge-id") for el in edge_groups} == {b["sceneEdgeId"] for b in meta["renderedBindings"]}
            body = {}
            for nid, group in groups.items():
                rects = [el for el in group if el.tag == NS + "rect" and el.get("stroke-width")]
                assert len(rects) == 1
                body[nid] = {k: float(rects[0].get(k)) for k in ("x", "y", "width", "height")}
            snapshots[label] = {"body": body, "svg": svg, "metadata": meta}
        except (AssertionError, KeyError, ValueError) as error:
            canonical_failures.append({"snapshot": label, "error": repr(error)})
check("32 public SVG snapshots bind canonical facts/visible bindings", len(snapshots) == 32 and not canonical_failures, canonical_failures)

trial_rows = read(AUDIT / "trial-audit.json")
trial_checks = []
for trial, row in zip(raw["trials"], trial_rows):
    events = [e for e in raw["events"] if e["trialId"] == trial["id"]]
    frames = [f for f in raw["frames"] if f["trialId"] == trial["id"]]
    down = next(e for e in events if e["trusted"] and e["type"] == "pointerdown")
    up = next(e for e in events if e["trusted"] and e["type"] == "pointerup" and e["pointerId"] == down["pointerId"] and e["eventAt"] >= down["eventAt"])
    active_frames = [f for f in frames if down["eventAt"] <= f["at"] <= up["eventAt"]]
    intervals = [b["at"] - a["at"] for a, b in zip(active_frames, active_frames[1:])]
    okay = row["recordedTrialFrames"] == len(frames) and row["recordedActiveGestureFrames"] == len(active_frames) and row["activeCallbackIntervalP95Ms"] == quantile95(intervals) and row["activeCallbackMaxIntervalMs"] == (max(intervals) if intervals else None)
    changed = []
    previous = geometry_signature(trial["before"])
    for frame in frames:
        current = geometry_signature(frame["geometry"])
        if current != previous:
            changed.append(frame)
        previous = current
    proxies = []
    for event in events:
        if not event["trusted"] or event["type"] not in ("pointermove", "wheel"):
            continue
        later = next((f for f in changed if f["observedAt"] >= event["capturedAt"]), None)
        proxies.append({"inputId": event["id"], "observedAt": later["observedAt"] if later else None, "inputToObservedChangeProxyMs": later["observedAt"] - event["eventAt"] if later else None, "presentedPaintCertified": False, "causalInputIdentified": False})
    okay &= proxies == row["continuousProxies"]
    if row["operation"] == "drag":
        nid = trial["spec"]["targetIds"][0]
        a = snapshots[trial["id"] + "-before"]["body"][nid]
        b = snapshots[trial["id"] + "-after"]["body"][nid]
        okay &= row["bodyBefore"] == a and row["bodyAfter"] == b and row["actualCanvasDelta"] == {k: b[k] - a[k] for k in ("x", "y")}
    if row["operation"] == "pan":
        a = trial["before"]["camera"]["matrix"]
        b = trial["after"]["camera"]["matrix"]
        dx = up["x"] - up["viewport"]["x"] - down["x"] + down["viewport"]["x"]
        dy = up["y"] - up["viewport"]["y"] - down["y"] + down["viewport"]["y"]
        expected = {**a, "e": a["e"] + dx, "f": a["f"] + dy}
        okay &= all(abs(expected[k] - b[k]) < .001 for k in b) and row["independentRecordedTerminalCamera"]["expected"] == expected
        okay &= row["existingValidatorOperationSucceeded"] is False
    trial_checks.append({"trial": trial["id"], "passed": bool(okay), "recordedFrames": len(frames), "activeGestureFrames": len(active_frames), "proxyMatches": len(proxies), "nullProxies": sum(p["observedAt"] is None for p in proxies)})
check("16 trials callback/proxy/directional geometry arithmetic", all(t["passed"] for t in trial_checks), trial_checks)

restore = read(AUDIT / "public-restoration-audit.json")
restore_pairs = [(raw["trials"][a - 1]["before"], raw["trials"][b - 1]["after"]) for a, b in ((1, 2), (4, 5), (6, 7), (8, 9))] + [(raw["trials"][0]["after"], raw["trials"][2]["after"]), (raw["trials"][14]["before"], raw["trials"][15]["after"])]
restore_okay = []
for (a, b), row in zip(restore_pairs, restore):
    actual = {"svgEqualExceptPublicRevision": norm_svg(a) == norm_svg(b), "frontierEqual": a["visibleIds"] == b["visibleIds"] and a["expandedIds"] == b["expandedIds"], "pinsEqual": a["pinnedIds"] == b["pinnedIds"], "selectionMarkupEqual": a["selectionMarkup"] == b["selectionMarkup"], "cameraEqual": a["camera"] == b["camera"]}
    restore_okay.append(all(row[k] == v for k, v in actual.items()))
check("six public restoration comparisons, including first selection inequality", all(restore_okay) and restore[0]["selectionMarkupEqual"] is False)

executions = []
oracle_rows = read(AUDIT / "routing-body-audit.json")
for row in oracle_rows:
    scene_path = AUDIT / row["scene"]
    scene = read(scene_path)
    public = snapshots[row["trialId"] + "-" + row["snapshot"]]
    check(row["scene"] + " direct XML body geometry", all({k: n[k] for k in ("x", "y", "width", "height")} == public["body"][n["id"]] for n in scene["nodes"]))
    groups = {el.get("data-edge-id"): el for el in public["svg"].iter() if el.get("data-edge-id")}
    check(row["scene"] + " raw path geometry", all(e["path"] == next(el for el in groups[e["id"]] if el.tag == NS + "path").get("d") for e in scene["edges"]))
    process = subprocess.run(["node", "--experimental-strip-types", str(ROOT / "docs/evidence/m4-bcf-browser-matrix-work/routing-quality/analyze_scene.ts"), str(scene_path)], text=True, capture_output=True)
    metric = json.loads(process.stdout) if process.returncode == 0 else None
    stored = read(AUDIT / row["scene"].replace(".public-xml-scene.json", ".routing.json"))
    check(row["scene"] + " independent oracle rerun exact", metric == stored and process.returncode == 0, {"exitCode": process.returncode})
    executions.append({"scene": str(scene_path), "exitCode": process.returncode, "stdoutSha256": hashlib.sha256(process.stdout.encode()).hexdigest(), "stderr": process.stderr})

buffer_ok = raw["buffers"]["frames"]["dropped"] == raw["buffers"]["overhead.frameCallbacks"]["dropped"] == 4102 and raw["buffers"]["events"]["dropped"] == raw["buffers"]["eventTiming"]["dropped"] == 0
check("incomplete frame / complete event scope retained", buffer_ok and summary["globalExistingValidatorCompleteBuffers"] is False and summary["lastStoredFrameAt"] == raw["frames"][-1]["at"])
check("no pin / human / publication / presented / hidden Canvas overclaim", all(not t["spec"]["pinnedIds"] for t in raw["trials"]) and all(summary[k] is False for k in ("humanCertified", "publicationCertified", "presentedPerformanceCertified", "hiddenCanvasCertified", "originalOperationJournalAvailable")))
check("all bound inputs and audit outputs unchanged during review", initial == [digest(path) for path in bound_paths])

result = {"schema": "archcanvas-independent-native-audit-review/1", "createdAtUTC": datetime.now(timezone.utc).isoformat(), "reviewedAudit": str(AUDIT), "status": "no-actionable-findings" if not findings else "findings", "findings": findings, "checks": checks, "oracleReruns": executions, "inputBindings": initial, "limitations": ["Read-only artifact review; no browser replay, model execution or product edits", "No second independent routing algorithm; existing independent oracle rerun and raw XML binding rechecked", "Canonical facts come from sealed static architecture only; no current saved gesture Canvas inferred", "Bilateral Event Timing covers 35 of 44 assigned inputs / 15 unique interactions only; p95 3008ms is not full-page INP", "Frame buffers lost 4102; recorded callbacks/proxies do not certify presented paint or smoothness", "Public pan terminal facts do not overturn global existing-validator failure", "Empty pin specs establish no pin protection; selection markup differs after first undo", "AI review contributes no real-human or publication acceptance"]}
with (HERE / "review.json").open("x") as stream:
    json.dump(result, stream, ensure_ascii=False, indent=2)
    stream.write("\n")
markdown = "Independent native observation audit review\n\n" + ("No actionable arithmetic, binding, manifest, or scope findings were found.\n\n" if not findings else "Findings: " + json.dumps(findings, ensure_ascii=False) + "\n\n") + "Rechecked all 108 input and 34 output bindings, 70-chunk reassembly, 32 public SVG snapshots, 16 trial callback/proxy calculations, six restoration comparisons and seven oracle reruns. Bilateral native timing remains 35/44 assigned inputs, 15 unique interactions, matched-subset p95 3008 ms.\n\nThe audit retains incomplete frame buffers (4,102 dropped each), complete event buffers, null later callback evidence, existing pan validator failures, empty pin specs and first-undo selection inequality. It makes no saved-Canvas, presented-paint, smoothness, human, or publication acceptance claim.\n\nThis is read-only artifact review, with no browser replay and no second routing oracle. Canonical architecture supplies facts only. Raw captures, frozen audit outputs, product files and old failed audit directories were unchanged.\n"
(HERE / "review.md").write_text(markdown)
outputs = [digest(path) for path in sorted(HERE.iterdir()) if path.is_file()]
with (HERE / "manifest.json").open("x") as stream:
    json.dump({"schema": "archcanvas-native-audit-review-manifest/1", "inputs": initial, "outputs": outputs}, stream, ensure_ascii=False, indent=2)
    stream.write("\n")
print(json.dumps({"status": result["status"], "checks": len(checks), "failedChecks": len(findings), "manifest": digest(HERE / "manifest.json")}, ensure_ascii=False))
