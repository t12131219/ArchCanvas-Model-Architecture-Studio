"""Independent geometry, XML boundary and current-document export checks."""

import hashlib
import io
import json
import re
import shutil
import struct
import subprocess
import sys
import tempfile
import unittest
import xml.etree.ElementTree as ET
from pathlib import Path

from archcanvas_publication import PublicationError, capabilities, export_svg

ROOT = Path(__file__).resolve().parents[1]
SVG = '<svg xmlns="http://www.w3.org/2000/svg" width="180mm" height="90mm" viewBox="0 0 200 100"><defs><marker id="arrow" viewBox="0 0 10 10" refX="9" refY="5" markerWidth="5" markerHeight="5" orient="auto"><path d="M1 1L9 5L1 9Z" fill="#345678"/></marker></defs><rect width="200" height="100" fill="#ffffff"/><g font-family="Arial, sans-serif"><text x="10" y="30" font-size="14" fill="#123456">Current edited title</text><path d="M10 50H180" fill="none" stroke="#345678" marker-end="url(#arrow)"/></g></svg>'
AVAILABLE = capabilities()


def chunks(png):
    cursor = 8
    while cursor < len(png):
        length = struct.unpack(">I", png[cursor:cursor + 4])[0]
        kind = png[cursor + 4:cursor + 8]
        yield kind, png[cursor + 8:cursor + 8 + length]
        cursor += length + 12


class PublicationTests(unittest.TestCase):
    def test_monochrome_role_legend_survives_all_publication_formats(self):
        # Literal publication vocabulary, independent of the Studio resolver.
        patterns = {"data": None, "residual": "9 4", "memory": "9 3 1 3", "mask": "3 3"}
        groups = []
        for index, (role, pattern) in enumerate(patterns.items()):
            dash = f' stroke-dasharray="{pattern}"' if pattern else ""
            groups.append(f'<g data-edge-legend-id="edge-role-legend:{role}:1" data-edge-role="{role}">'
                          f'<path d="M10 {20 + index * 20}H50" stroke="#56616b" stroke-width="1.5"{dash} marker-end="url(#arrow)"/>'
                          f'<text x="70" y="{20 + index * 20}" font-size="10">{role}</text></g>')
        source = SVG.replace('<g font-family="Arial, sans-serif">', ''.join(groups) + '<g font-family="Arial, sans-serif">')
        for width in (85, 180):
            exported = export_svg(source, "svg", width)
            parsed = ET.fromstring(exported["data"])
            for role, pattern in patterns.items():
                group = parsed.find(f'.//{{http://www.w3.org/2000/svg}}g[@data-edge-role="{role}"]')
                self.assertIsNotNone(group)
                self.assertEqual(group.get("data-edge-legend-id"), f"edge-role-legend:{role}:1")
                path = group.find('{http://www.w3.org/2000/svg}path')
                self.assertEqual(path.get("stroke-dasharray"), pattern)
                self.assertEqual(path.get("marker-end"), "url(#arrow)")
            self.assertEqual(exported["receipt"]["outputDigest"], hashlib.sha256(exported["data"]).hexdigest())
            if AVAILABLE["png"] and AVAILABLE["pdf"]:
                self.assertTrue(export_svg(source, "png", width)["data"].startswith(b"\x89PNG"))
                self.assertTrue(export_svg(source, "pdf", width)["data"].startswith(b"%PDF-"))

    def test_role_legend_vocabulary_keeps_external_and_executable_attributes_rejected(self):
        literal = '<g data-edge-legend-id="edge-role-legend:memory:1" data-edge-role="memory"/>'
        for group in [literal.replace('data-edge-role="memory"', 'data-edge-role="invented"'),
                      literal.replace('edge-role-legend:memory:1', 'url(https://example.org/x)'),
                      literal.replace('edge-role-legend:memory:1', 'invalid id'),
                      literal.replace('/>', ' onclick="alert(1)"/>'),
                      literal.replace('/>', ' href="https://example.org/x"/>'),
                      literal.replace('data-edge-legend-id', 'data-arbitrary-script')]:
            source = SVG.replace('<defs>', group + '<defs>')
            for format in ("svg", "png", "pdf"):
                with self.subTest(group=group, format=format), self.assertRaises(PublicationError):
                    export_svg(source, format)

    def test_svg_preserves_current_text_and_physical_aspect(self):
        for width in (85, 180):
            result = export_svg(SVG, "svg", width, 300)
            parsed = ET.fromstring(result["data"])
            self.assertEqual(parsed.get("width"), f"{width}mm")
            self.assertEqual(float(parsed.get("height").removesuffix("mm")), width / 2)
            self.assertEqual(parsed.get("viewBox"), "0 0 200 100")
            self.assertIn("Current edited title", result["data"].decode())
            self.assertEqual(result["mime"], "image/svg+xml")
            self.assertTrue(result["receipt"]["geometryVerified"])
            self.assertFalse(result["receipt"]["fonts"]["embeddingGuaranteed"])
            self.assertEqual(result["receipt"]["outputDigest"], hashlib.sha256(result["data"]).hexdigest())

    @unittest.skipUnless(AVAILABLE["png"] and AVAILABLE["pdf"], "Project-local CairoSVG converter is unavailable")
    def test_png_pixels_density_and_pdf_page_dimensions_at_85_180_mm(self):
        for width, expected_width, expected_height in ((85, 1004, 502), (180, 2126, 1063)):
            png = export_svg(SVG, "png", width, 300)
            self.assertEqual(png["data"][:8], b"\x89PNG\r\n\x1a\n")
            self.assertEqual(struct.unpack(">II", png["data"][16:24]), (expected_width, expected_height))
            metadata = dict(chunks(png["data"]))
            density = struct.unpack(">IIB", metadata[b"pHYs"])
            self.assertEqual(density, (11811, 11811, 1))
            self.assertAlmostEqual(density[0] * 0.0254, 300, delta=0.01)
            self.assertEqual(png["receipt"]["pixelDimensions"], [expected_width, expected_height])
            pdf = export_svg(SVG, "pdf", width, 300)
            self.assertTrue(pdf["data"].startswith(b"%PDF-"))
            # Independently read the actual uncompressed Cairo page box.
            box = re.search(rb"/MediaBox\s*\[([^\]]+)\]", pdf["data"])
            values = [float(item) for item in box.group(1).split()]
            self.assertAlmostEqual(values[2] - values[0], width / 25.4 * 72, delta=0.01)
            self.assertAlmostEqual(values[3] - values[1], width / 2 / 25.4 * 72, delta=0.01)
            self.assertEqual(pdf["mime"], "application/pdf")
            self.assertTrue(pdf["receipt"]["geometryVerified"])

    def test_executable_external_and_css_inputs_are_rejected_before_conversion(self):
        unsafe = [
            '<!DOCTYPE svg [<!ENTITY data SYSTEM "file:///etc/passwd">]>' + SVG.replace("Current edited title", "&data;"),
            SVG.replace("<defs>", '<script>alert(1)</script><defs>'),
            SVG.replace("<defs>", '<foreignObject><div>HTML</div></foreignObject><defs>'),
            SVG.replace("<defs>", '<image href="file:///etc/passwd"/><defs>'),
            SVG.replace("<defs>", '<use href="https://example.org/evil.svg"/><defs>'),
            SVG.replace('fill="#ffffff"', 'fill="url(https://example.org/style)"'),
            SVG.replace('<g font-family', '<g onclick="alert(1)" font-family'),
            SVG.replace('<g font-family', '<g style="fill:red" font-family'),
            SVG.replace("<defs>", '<style>@import "https://example.org/style";</style><defs>'),
            SVG.replace("url(#arrow)", "url(file:///tmp/arrow.svg#x)"),
            SVG.replace("url(#arrow)", "url(#missing)"),
            '<?xml-stylesheet href="file:///tmp/styles.css"?>' + SVG,
            SVG.replace('xmlns="http://www.w3.org/2000/svg"', 'xmlns="https://example.org/fake"'),
            SVG.replace("<defs>", '<animate attributeName="x"/><defs>'),
            SVG.replace('fill="#345678"/>', 'fill="#345678" marker-end="url(#arrow)"/>', 1),
        ]
        for source in unsafe:
            for format in ("svg", "pdf", "png"):
                with self.subTest(source=source[:60], format=format), self.assertRaises(PublicationError):
                    export_svg(source, format)

    def test_size_number_and_resource_budgets(self):
        for width in (True, float("nan"), 10, 1001):
            with self.assertRaises(PublicationError):
                export_svg(SVG, "svg", width)
        for dpi in (True, 71, 1201, 300.5):
            with self.assertRaises(PublicationError):
                export_svg(SVG, "png", 180, dpi)
        for source in (SVG.replace('viewBox="0 0 200 100"', 'viewBox="0 0 0 100"'), SVG.replace('x="10"', 'x="NaN"'), "x" * 8_000_001):
            with self.assertRaises(PublicationError):
                export_svg(source, "svg")
        with self.assertRaises(PublicationError):
            export_svg(SVG.replace("<defs>", "<g>" * 65 + "</g>" * 65 + "<defs>"), "svg")
        with self.assertRaises(PublicationError):
            export_svg(SVG, "html")

    def test_cli_binary_output_and_capability_provenance(self):
        command = [sys.executable, "-I", "-B", "-c", f"import runpy,sys; sys.path.insert(0,{str(ROOT / 'src')!r}); runpy.run_module('archcanvas_publication',run_name='__main__')"]
        converted = subprocess.run(command + ["--format", "svg", "--width-mm", "85"], input=SVG.encode(), capture_output=True, timeout=10)
        self.assertEqual(converted.returncode, 0, converted.stderr.decode())
        self.assertTrue(converted.stdout.startswith(b"<svg"))
        self.assertEqual(json.loads(converted.stderr)["widthMm"], 85)
        advertised = subprocess.run(command + ["--capabilities"], capture_output=True, timeout=10)
        evidence = json.loads(advertised.stdout)
        self.assertTrue(Path(evidence["moduleOrigin"]).is_relative_to(ROOT / "src"))
        self.assertFalse(evidence["fontEmbeddingGuaranteed"])

    @unittest.skipUnless(AVAILABLE["png"] and AVAILABLE["pdf"], "Project-local CairoSVG converter is unavailable")
    def test_real_cjk_glyphs_png_and_pdf_text_are_preserved(self):
        import cairocffi as cairo
        from PIL import Image
        surface = cairo.ImageSurface(cairo.FORMAT_ARGB32, 1, 1)
        context = cairo.Context(surface)
        context.select_font_face("Noto Sans CJK SC")
        context.set_font_size(20)
        characters = "当前画布"
        glyphs = context.get_scaled_font().text_to_glyphs(0, 0, characters, False)
        if any(glyph[0] == 0 for glyph in glyphs):
            self.skipTest("The host does not provide Noto Sans CJK SC coverage; converter preflight will reject this publication.")
        self.assertEqual(len(glyphs), 4)
        self.assertTrue(all(glyph[0] > 0 for glyph in glyphs))
        source = f'<svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 240 80"><rect width="240" height="80" fill="#ffffff"/><text x="10" y="50" font-size="28" font-family="Noto Sans CJK SC, sans-serif" fill="#123456">{characters}</text></svg>'
        png = export_svg(source, "png", 85, 300)
        font_evidence = png["receipt"]["fonts"]["glyphCoverage"]
        self.assertEqual(font_evidence["status"], "passed")
        self.assertEqual(font_evidence["faces"][0]["selectedFamily"], "Noto Sans CJK SC")
        self.assertEqual(font_evidence["faces"][0]["missingCharacters"], [])
        missing_glyph_image = export_svg(source.replace(characters, "\u0378" * 4).replace("Noto Sans CJK SC, sans-serif", "DejaVu Sans"), "svg", 85)
        # Direct known-tofu rendering is an independent image counterexample;
        # the production converter must reject it via missing-glyph preflight.
        import cairosvg
        tofu = cairosvg.svg2png(bytestring=missing_glyph_image["data"], output_width=1004, output_height=335)
        actual_image = Image.open(io.BytesIO(png["data"])).convert("RGB")
        tofu_image = Image.open(io.BytesIO(tofu)).convert("RGB")
        self.assertNotEqual(actual_image.tobytes(), tofu_image.tobytes())
        with self.assertRaisesRegex(PublicationError, "missing glyphs"):
            export_svg(source.replace("Noto Sans CJK SC, sans-serif", "DejaVu Sans"), "png", 85)
        pdf = export_svg(source, "pdf", 85, 300)
        if shutil.which("pdftotext"):
            with tempfile.TemporaryDirectory() as directory:
                path = Path(directory) / "cjk.pdf"
                path.write_bytes(pdf["data"])
                extracted = subprocess.run(["pdftotext", str(path), "-"], capture_output=True, timeout=10)
                self.assertEqual(extracted.returncode, 0)
                self.assertIn(characters, extracted.stdout.decode("utf-8"))

    @unittest.skipUnless(shutil.which("node"), "Node is unavailable")
    def test_same_ts_scene_script_uses_current_document_and_escapes_labels(self):
        with tempfile.TemporaryDirectory() as directory:
            temporary = Path(directory)
            document_path = temporary / "current.json"
            output_path = temporary / "current.svg"
            # The scene is generated by the formal core, not reconstructed in
            # Python. The only input edits are CanvasDocument visual fields.
            bootstrap = '''import fs from 'node:fs';
import {createDocument,applyVisualBatch} from './studio/src/core/index.ts';
const a=JSON.parse(fs.readFileSync(process.argv[1]));
const d=createDocument(a);
const input=a.nodes.find(n=>n.kind==='Input');
const next=applyVisualBatch(d,[{type:'alias',id:input.id,label:'CURRENT <edited> & label'},{type:'legend',items:[{id:'manual',label:'CURRENT manual legend',color:'#123456',glyph:'module'}]},{type:'annotation',annotation:{id:'cjk',text:'当前画布',x:50,y:400}}]);
fs.writeFileSync(process.argv[2],JSON.stringify(next));
'''
            from archcanvas_python import analyze_project
            architecture_path = temporary / "architecture.json"
            architecture_path.write_text(json.dumps(analyze_project(ROOT / "fixtures/mlp", "model:MLP")))
            created = subprocess.run(["node", "--experimental-strip-types", "--input-type=module", "-e", bootstrap, str(architecture_path), str(document_path)], cwd=ROOT, capture_output=True, timeout=15)
            self.assertEqual(created.returncode, 0, created.stderr.decode())
            original_bytes = document_path.read_bytes()
            rendered = subprocess.run(["node", "--experimental-strip-types", "scripts/export_canvas.mjs", "--document", str(document_path), "--output", str(output_path), "--format", "svg", "--python", sys.executable], cwd=ROOT, capture_output=True, timeout=15)
            self.assertEqual(rendered.returncode, 0, rendered.stderr.decode())
            svg = output_path.read_text()
            self.assertIn("CURRENT &lt;edited&gt; &amp; label", svg)
            self.assertIn("CURRENT manual legend", svg)
            self.assertIn("当前画布", svg)
            self.assertIn('font-family="Noto Sans CJK SC,', svg)
            self.assertNotIn("data-expand-id", svg)
            self.assertEqual(document_path.read_bytes(), original_bytes)
            receipt = json.loads(Path(str(output_path) + ".receipt.json").read_text())
            current = json.loads(document_path.read_text())
            self.assertEqual(receipt["documentId"], current["id"])
            self.assertEqual(receipt["revision"], current["revision"])
            self.assertEqual(receipt["sourceDigest"], current["architecture"]["sourceDigest"])
            self.assertEqual(receipt["irDigest"], current["architecture"]["irDigest"])
            self.assertEqual(receipt["sceneSvgDigest"], receipt["inputSvgDigest"])


if __name__ == "__main__":
    unittest.main()
