"""Read actual copied browser artifacts; produce separately labelled review rasters."""
from pathlib import Path
import hashlib
import json
import sys
import xml.etree.ElementTree as ET

import cairosvg
from PIL import Image

FORMAL = Path(__file__).resolve().parents[4]
WORK = Path(__file__).resolve().parent
SOURCE = FORMAL / "docs/evidence/m4-monochrome-role-work/browser-current"


def binding(path):
    data = path.read_bytes()
    return {"path": str(path.relative_to(FORMAL)), "bytes": len(data), "sha256": hashlib.sha256(data).hexdigest()}


def main(case):
    source = SOURCE / case
    target = WORK / case
    target.mkdir(exist_ok=False)
    inputs = sorted(path for path in source.iterdir() if path.is_file())
    before = [binding(path) for path in inputs]
    (target / "inputs-before.json").write_text(json.dumps(before, indent=2) + "\n")
    svgpath = source / "figure.svg"
    root = ET.fromstring(svgpath.read_bytes())
    viewbox = list(map(float, root.attrib["viewBox"].split()))
    pngpath = target / "actual-publication-svg-converted.png"
    cairosvg.svg2png(bytestring=svgpath.read_bytes(), write_to=str(pngpath), output_width=round(viewbox[2]*2), output_height=round(viewbox[3]*2))
    img = Image.open(pngpath)
    crops = []
    # Full-width upper/frontier and footer crops retain the actual conversion pixels.
    for name, box in [("frontier", (0, 0, img.width, min(img.height, 1000))), ("footer", (0, max(0, img.height - 500), img.width, img.height))]:
        crop = target / f"actual-publication-svg-converted-{name}.png"
        img.crop(box).save(crop)
        crops.append({"name":name, "box":list(box), **binding(crop)})
    edgefacts = []
    legends = []
    for el in root.iter():
        if "data-edge-id" in el.attrib:
            visible = next((child for child in el if child.tag.endswith("path") and child.attrib.get("stroke") != "transparent"), None)
            if visible is not None:
                edgefacts.append({"id": el.attrib["data-edge-id"], "role":el.attrib.get("data-edge-role"), "stroke": visible.attrib.get("stroke"), "width":visible.attrib.get("stroke-width"), "dasharray":visible.attrib.get("stroke-dasharray"), "d":visible.attrib.get("d")})
        if "data-edge-legend-id" in el.attrib:
            legends.append({"id":el.attrib["data-edge-legend-id"], "role":el.attrib.get("data-edge-role"), "paths":[c.attrib for c in el if c.tag.endswith("path")], "texts":["".join(c.itertext()) for c in el if c.tag.endswith("text")]})
    statefacts = []
    for beforepath in source.glob("*-before.json"):
        afterpath = source / beforepath.name.replace("-before.json", "-after.json")
        b = json.loads(beforepath.read_text())
        a = json.loads(afterpath.read_text()) if afterpath.exists() else None
        keys = ["camera", "dataset", "viewport", "url"]
        bm = {k:b.get(k) for k in keys}
        am = {k:a.get(k) for k in keys} if a else None
        statefacts.append({"before":beforepath.name, "after":afterpath.name if a else None, "beforeState":bm, "afterState":am, "stateEqual":bm==am if a else None})
    receipt = {"case":case, "kind":"actual-publication-svg-conversion-for-AI-observation", "notBrowserPngExport":True, "modelExecuted":False, "physicalFontOrHumanCertification":False, "viewBox":viewbox, "rasterScale":2, "inputSvg":binding(svgpath), "conversion":binding(pngpath), "crops":crops, "interpreter":sys.executable, "cairoSvgOrigin":cairosvg.__file__, "imageOrigin":Image.__file__, "edgeFacts":edgefacts, "roleLegends":legends, "imageStatePairs":statefacts, "beforeBindings":before, "afterBindings":[binding(path) for path in inputs]}
    receipt["allInputsUnchanged"] = receipt["beforeBindings"] == receipt["afterBindings"]
    (target / "conversion-receipt.json").write_text(json.dumps(receipt, indent=2, ensure_ascii=False) + "\n")
    print(json.dumps({"case":case,"inputs":len(inputs),"unchanged":receipt["allInputsUnchanged"],"states": [{"before":f["before"],"stateEqual":f["stateEqual"]} for f in statefacts],"viewBox":viewbox,"edgeFacts":edgefacts,"roleLegends":legends}, ensure_ascii=False))


if __name__ == "__main__":
    main(sys.argv[1])
