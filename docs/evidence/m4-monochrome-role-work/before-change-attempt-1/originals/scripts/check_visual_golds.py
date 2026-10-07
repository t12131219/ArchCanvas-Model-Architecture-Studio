#!/usr/bin/env python3
"""Render and independently audit real-source visual gold candidates.

This produces evidence, including unmet publication recommendations. A successful
command means the audit completed; it does not mean human visual acceptance or
browser interaction has passed. No fixture is modified and no other renderer is
introduced. The formal TypeScript Scene/SVG and publication converter are used.
"""

from __future__ import annotations

import argparse
import json
from pathlib import Path
import shutil
import subprocess
import sys
import tempfile
import xml.etree.ElementTree as ET

from check_independence import clean_environment
from check_stage2 import command, python_args


CREATOR = r'''
import {readFile,writeFile} from 'node:fs/promises';
const {createDocument,applyVisualBatch,buildScene,renderSvg}=await import(process.argv[2]);
const output=process.argv[3];
const facts=(scene)=>new Map(scene.nodes.map(n=>[n.id,{x:n.x,y:n.y,width:n.width,height:n.height}]));
const same=(a,b)=>JSON.stringify(a)===JSON.stringify(b);
const reports=[];
for(const fixture of ['transformer','mlp','residual_cnn']) {
  const a=JSON.parse(await readFile(`${output}/${fixture}.architecture.json`,'utf8'));
  const by=new Map(a.nodes.map(n=>[n.id,n]));
  const depth=(node)=>{let n=node,d=0;while(n.parentId){d++;n=by.get(n.parentId)}return d};
  let d=createDocument(a),base=buildScene(d);
  const pin=base.nodes.find(n=>!n.children && n.category==='output') ?? base.nodes.find(n=>n.category==='output');
  const pinNode=base.nodes.find(n=>n.id===pin?.id);
  const initialPin=pinNode && {x:pinNode.x,y:pinNode.y};
  let pinnedDocument=pinNode?applyVisualBatch(d,[{type:'pin',ids:[pinNode.id],pinned:true}]):d;
  // A representative full frontier at each available authored containment depth.
  // A shallow model is not advertised as having three recovered hierarchy levels.
  const maxDepth=Math.max(...a.nodes.filter(n=>n.children.length).map(depth));
  const continuity=[];
  for(let level=0;level<=Math.min(3,maxDepth);level++) {
    if(level>0)for(const n of a.nodes.filter(n=>n.children.length && depth(n)===level)) {
      const before=buildScene(d),anchor=before.nodes.find(v=>v.id===n.id);
      d=applyVisualBatch(d,[{type:'expand',id:n.id,expanded:true}]);
      pinnedDocument=applyVisualBatch(pinnedDocument,[{type:'expand',id:n.id,expanded:true}]);
      const after=buildScene(d),current=after.nodes.find(v=>v.id===n.id),pinned=buildScene(pinnedDocument).nodes.find(v=>v.id===pinNode?.id);
      continuity.push({operatedId:n.id,level,anchorBefore:{x:anchor?.x,y:anchor?.y},anchorAfter:{x:current?.x,y:current?.y},
        anchorUnchanged:anchor?.x===current?.x&&anchor?.y===current?.y,
        pinUnchanged:!initialPin||(pinned?.x===initialPin.x&&pinned?.y===initialPin.y)});
    }
    for(const preset of ['paper','monochrome'])for(const widthMm of [85,180]) {
      const current=applyVisualBatch(d,[{type:'page',page:{preset,widthMm}}]);
      const scene=buildScene(current),name=`${fixture}-level${level}-${preset}-${widthMm}`;
      await writeFile(`${output}/${name}.canvas.json`,JSON.stringify(current));
      await writeFile(`${output}/${name}.scene.json`,JSON.stringify(scene));
      await writeFile(`${output}/${name}.svg`,renderSvg(scene));
      const represented=scene.edges.flatMap(e=>e.canonicalEdgeIds).concat(scene.hiddenEdges);
      const edgeCoverage=same([...represented].sort(),a.edges.map(e=>e.id).sort());
      const endpointChecks=scene.edges.map(e=>{
        const source=scene.nodes.find(n=>n.id===e.sourceId),target=scene.nodes.find(n=>n.id===e.targetId);
        const sp=source.ports.find(p=>p.canonicalEdgeIds.includes(e.id)&&p.direction==='out');
        const tp=target.ports.find(p=>p.canonicalEdgeIds.includes(e.id)&&p.direction==='in');
        const tokens=[...e.path.matchAll(/([MVH])\s*(-?[\d.]+)(?:\s+(-?[\d.]+))?/g)];
        let x=0,y=0;const points=[];
        for(const [,op,first,second]of tokens){if(op==='M'){x=+first;y=+second}else if(op==='V')y=+first;else x=+first;points.push({x,y})}
        // Scene routes round coordinates to 0.1 model units, SVG to 0.01.
        const close=(p,q)=>p&&q&&Math.abs(p.x-q.x)<=.051&&Math.abs(p.y-q.y)<=.051;
        return {id:e.id,passed:!!sp&&!!tp&&close(points[0],sp)&&close(points.at(-1),tp)};
      });
      const glyphMeaning=scene.nodes.every(n=>!!n.glyph&&!!n.label)&&scene.edges.filter(e=>e.role==='mask').every(e=>e.dashed);
      const overlap=(p,q)=>p.x<q.x+q.width&&p.x+p.width>q.x&&p.y<q.y+q.height&&p.y+p.height>q.y;
      const siblingOverlaps=scene.nodes.flatMap((node,i)=>scene.nodes.slice(i+1).filter(other=>node.parentId===other.parentId&&overlap(node,other)).map(other=>[node.id,other.id]));
      reports.push({name,fixture,level,preset,widthMm,sceneWidth:scene.bounds.width,sceneHeight:scene.bounds.height,
        sourceDigest:scene.sourceDigest,irDigest:scene.irDigest,edgeCoverage,endpointChecks,
        monochromeMeaningViaLabelsGlyphsAndMaskDashes:glyphMeaning,siblingOverlaps,visibleNodes:scene.nodes.length,visibleEdges:scene.edges.length});
    }
  }
  // Restore the complete base frontier. Geometry recovery is separate from visual undo.
  for(const n of [...a.nodes].reverse().filter(n=>n.children.length&&d.expandedIds.includes(n.id)&&depth(n)>0))
    d=applyVisualBatch(d,[{type:'expand',id:n.id,expanded:false}]);
  const restored=buildScene(d),restore=facts(restored),original=facts(base);
  const geometryRestored=[...original].every(([id,b])=>same(restore.get(id),b));
  await writeFile(`${output}/${fixture}-continuity.json`,JSON.stringify({maxAuthoredContainerDepth:maxDepth,continuity,
    anchorAndPinPassed:continuity.every(c=>c.anchorUnchanged&&c.pinUnchanged),baseGeometryRestored:geometryRestored,
    pinnedConflictDiagnostics:buildScene(pinnedDocument).diagnostics.filter(d=>d.message.includes('overlaps expanded'))},null,2));
}
await writeFile(`${output}/scene-audit.json`,JSON.stringify(reports,null,2));
'''


def check(project: Path, interpreter: Path, output: Path, png: bool) -> Path:
    output.mkdir(parents=True, exist_ok=True)
    environment = clean_environment(output)
    for fixture, entry in (("transformer", "model:Transformer"), ("mlp", "model:MLP"), ("residual_cnn", "model:ResidualCNN")):
        analysis = (
            "import json; from pathlib import Path; from archcanvas_python import analyze_project; "
            f"Path({str(output / (fixture + '.architecture.json'))!r}).write_text(json.dumps(analyze_project({str(project / 'fixtures' / fixture)!r},{entry!r})),encoding='utf-8')"
        )
        command(python_args(interpreter, project, analysis), project, environment)
    creator = output / "create-visual-golds.mjs"
    creator.write_text(CREATOR, encoding="utf-8")
    node = shutil.which("node")
    if not node:
        raise RuntimeError("Formal renderer requires Node 24+")
    command([node, str(creator), (project / "studio/src/core/index.ts").as_uri(), str(output)], project, environment)
    variants = json.loads((output / "scene-audit.json").read_text(encoding="utf-8"))
    for variant in variants:
        svg = output / (variant["name"] + ".svg")
        root = ET.fromstring(svg.read_bytes())
        width_mm = float(root.attrib["width"].removesuffix("mm"))
        viewbox_width = float(root.attrib["viewBox"].split()[2])
        scale_pt = width_mm / viewbox_width * 72 / 25.4
        texts = [float(e.attrib["font-size"]) for e in root.iter() if "font-size" in e.attrib]
        paths = [float(e.attrib["stroke-width"]) for e in root.iter() if "stroke-width" in e.attrib]
        variant["physicalPreflight"] = {
            "mmWidth": width_mm,
            "minTextPt": round(min(texts) * scale_pt, 3),
            "nodeLabelPt": round(13 * scale_pt, 3),
            "mainLinePt": round(1.5 * scale_pt, 3),
            "minStrokePt": round(min(paths) * scale_pt, 3),
            "examplePreset": {"textPt": [7, 9], "mainLinePt": [0.5, 1]},
            "examplePresetMet": min(texts) * scale_pt >= 7 and 0.5 <= 1.5 * scale_pt <= 1,
            "scope": "Measured real-size SVG; example targets are configurable recommendations, not a universal journal rule.",
        }
        if png:
            target = output / (variant["name"] + ".png")
            code = (
                "from pathlib import Path; import json; from archcanvas_publication import export_svg; "
                f"receipt=export_svg(Path({str(svg)!r}).read_text(),format='png',width_mm={width_mm!r},dpi=300); "
                f"Path({str(target)!r}).write_bytes(receipt['data']); "
                f"Path({str(target) + '.receipt.json'!r}).write_text(json.dumps(receipt['receipt'],ensure_ascii=False,indent=2),encoding='utf-8')"
            )
            command(python_args(interpreter, project, code, allow_site=True), project, environment)
            variant["png"] = str(target)
    continuity = {fixture: json.loads((output / (fixture + "-continuity.json")).read_text())
                  for fixture in ("transformer", "mlp", "residual_cnn")}
    geometry = all(v["edgeCoverage"] and not v['siblingOverlaps'] and all(e["passed"] for e in v["endpointChecks"]) for v in variants)
    spatial = all(v["anchorAndPinPassed"] and v["baseGeometryRestored"] for v in continuity.values())
    report = {
        "schemaVersion": 1, "auditCompleted": True, "geometryPassed": geometry, "spatialCorePassed": spatial,
        "visualAcceptance": "pending-human-and-browser-review", "sourceProject": str(project), "artifacts": str(output),
        "variants": variants, "continuity": continuity,
        "limitations": [
            "Static core continuity is not a substitute for actual browser screen/camera interactions.",
            "PNG derivatives are publication artifacts, not Studio screenshots.",
            "Shallow authored models expose only recovered levels; no hierarchy is fabricated.",
            "A final font recommendation miss remains visible; scaling a whole wide scene is not a detailed-page export implementation.",
        ],
    }
    destination = output / "visual-gold-report.json"
    destination.write_text(json.dumps(report, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    return destination


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--project", type=Path, default=Path(__file__).resolve().parents[1])
    parser.add_argument("--python", type=Path)
    parser.add_argument("--output", type=Path)
    parser.add_argument("--png", action="store_true")
    options = parser.parse_args()
    output = options.output or Path(tempfile.mkdtemp(prefix="archcanvas-visual-golds-", dir="/tmp"))
    try:
        path = check(options.project.resolve(), options.python or options.project / ".venv/bin/python", output.resolve(), options.png)
    except (OSError, ValueError, RuntimeError, subprocess.TimeoutExpired) as error:
        print(json.dumps({"auditCompleted": False, "error": str(error)}, ensure_ascii=False), file=sys.stderr)
        return 1
    print(json.dumps({"auditCompleted": True, "report": str(path)}, ensure_ascii=False, indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
