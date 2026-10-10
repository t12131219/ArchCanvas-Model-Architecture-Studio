"""Validate a publication SVG before producing SVG, PDF or PNG bytes."""

from __future__ import annotations

import hashlib
import importlib
import math
import re
import struct
import sys
import xml.etree.ElementTree as ET
import zlib
from pathlib import Path
from typing import Any

SVG_NS = "http://www.w3.org/2000/svg"
MAX_SVG_BYTES = 8_000_000
MAX_ELEMENTS = 30_000
MAX_TEXT = 500_000
MAX_PIXELS = 40_000_000
ET.register_namespace("", SVG_NS)


class PublicationError(ValueError):
    """Invalid or unsupported publication input; no output was committed."""


COMMON = {
    "id", "fill", "stroke", "stroke-width", "stroke-linecap", "stroke-linejoin",
    "stroke-dasharray", "opacity", "fill-opacity", "stroke-opacity", "transform",
    "font-family", "font-size", "font-weight", "letter-spacing", "text-anchor",
    "aria-label", "role",
}
ATTRIBUTES = {
    "svg": {"width", "height", "viewBox", "preserveAspectRatio", "data-document-id", "data-revision"},
    "g": {"data-node-id", "data-canonical-id", "data-edge-id", "data-tensor-id", "data-legend-id", "data-annotation-id", "data-edge-legend-id", "data-edge-role", "data-source-relation-id", "data-source-relation-legend"},
    "rect": {"x", "y", "width", "height", "rx", "ry"},
    "circle": {"cx", "cy", "r", "data-port-id", "data-node-id"},
    "path": {"d", "marker-end", "marker-start", "marker-mid", "data-caption-guide-id", "data-caption-for-edge", "pointer-events"},
    "text": {"x", "y", "dx", "dy", "textLength", "lengthAdjust"},
    "tspan": {"x", "y", "dx", "dy"},
    "title": set(),
    "metadata": set(),
    "defs": set(),
    "marker": {"viewBox", "refX", "refY", "markerWidth", "markerHeight", "orient", "markerUnits"},
    "line": {"x1", "y1", "x2", "y2"},
    "polyline": {"points"},
    "polygon": {"points"},
    "ellipse": {"cx", "cy", "rx", "ry"},
}
NUMBER = re.compile(r"[-+]?(?:\d+(?:\.\d*)?|\.\d+)(?:[eE][-+]?\d+)?\Z")
COLOR = re.compile(r"#[0-9a-fA-F]{3}(?:[0-9a-fA-F]{3})?(?:[0-9a-fA-F]{2})?\Z")
ID = re.compile(r"[A-Za-z_][A-Za-z0-9_.:-]{0,255}\Z")
LOCAL_URL = re.compile(r"url\(\s*#([A-Za-z_][A-Za-z0-9_.:-]{0,255})\s*\)\Z")
NUMERIC_ATTRIBUTES = {
    "x", "y", "cx", "cy", "x1", "y1", "x2", "y2", "dx", "dy", "r", "rx", "ry",
    "stroke-width", "opacity", "fill-opacity", "stroke-opacity", "font-size", "letter-spacing",
    "refX", "refY", "markerWidth", "markerHeight", "textLength",
}
ENUMS = {
    "stroke-linecap": {"butt", "round", "square"},
    "stroke-linejoin": {"miter", "round", "bevel"},
    "text-anchor": {"start", "middle", "end"},
    "markerUnits": {"strokeWidth", "userSpaceOnUse"},
    "lengthAdjust": {"spacing", "spacingAndGlyphs"},
    "role": {"img"},
    "data-edge-role": {"data", "residual", "memory", "mask"},
    "pointer-events": {"none"},
}


def _hash(value: bytes) -> str:
    return hashlib.sha256(value).hexdigest()


def _number(value: str, location: str) -> float:
    if not NUMBER.fullmatch(value.strip()):
        raise PublicationError(f"{location} must be a finite SVG number.")
    number = float(value)
    if not math.isfinite(number) or abs(number) > 10_000_000:
        raise PublicationError(f"{location} exceeds the coordinate budget.")
    return number


def _numbers(value: str, location: str, count: int | None = None) -> list[float]:
    parts = re.split(r"[\s,]+", value.strip())
    if not parts or (count is not None and len(parts) != count):
        raise PublicationError(f"{location} needs {count or 'a list of'} SVG numbers.")
    return [_number(part, location) for part in parts]


def _tag(element: ET.Element) -> str:
    if not isinstance(element.tag, str) or not element.tag.startswith(f"{{{SVG_NS}}}"):
        raise PublicationError("Only elements in the SVG namespace are accepted.")
    name = element.tag[len(SVG_NS) + 2:]
    if name not in ATTRIBUTES:
        raise PublicationError(f"Unsupported publication element: {name}.")
    return name


def _validate(svg: str) -> tuple[ET.Element, tuple[float, float, float, float], list[str]]:
    if not isinstance(svg, str):
        raise PublicationError("SVG input must be UTF-8 text.")
    encoded = svg.encode("utf-8")
    if not encoded or len(encoded) > MAX_SVG_BYTES:
        raise PublicationError("SVG must fit within the 8 MB input budget.")
    if re.search(r"<!\s*(?:DOCTYPE|ENTITY)|<\?", svg, flags=re.I):
        raise PublicationError("DTD, entities and processing instructions are forbidden.")
    try:
        root = ET.fromstring(svg)
    except (ET.ParseError, RecursionError) as exc:
        raise PublicationError("SVG is not valid supported XML.") from exc
    if _tag(root) != "svg":
        raise PublicationError("The publication root must be svg.")
    if not root.get("viewBox"):
        raise PublicationError("A positive viewBox is required to preserve figure aspect ratio.")
    viewbox = tuple(_numbers(root.get("viewBox", ""), "svg.viewBox", 4))
    if viewbox[2] <= 0 or viewbox[3] <= 0 or viewbox[3] / viewbox[2] > 100:
        raise PublicationError("SVG viewBox dimensions or aspect ratio exceed the publication budget.")
    identifiers: set[str] = set()
    markers: set[str] = set()
    references: list[str] = []
    caption_guides: dict[str, str] = {}
    rendered_edges: set[str] = set()
    fonts: set[str] = set()
    count, text_size = 0, 0
    stack = [(root, 1, False)]
    while stack:
        element, depth, inside_definition = stack.pop()
        tag = _tag(element)
        if depth > 64:
            raise PublicationError("SVG exceeds the 64-level nesting budget.")
        if tag == "svg" and element is not root:
            raise PublicationError("Nested SVG viewports are outside the publication vocabulary.")
        if inside_definition and any(attribute in element.attrib for attribute in ("marker-end", "marker-start", "marker-mid")):
            raise PublicationError("Marker definitions cannot recursively reference other markers.")
        if inside_definition and any(attribute in element.attrib for attribute in ("data-caption-guide-id", "data-caption-for-edge", "pointer-events")):
            raise PublicationError("Caption decorations cannot occur inside marker definitions.")
        if tag == "defs" and any(_tag(child) != "marker" for child in element):
            raise PublicationError("Only local marker definitions are supported in defs.")
        if tag == "marker" and any(_tag(child) not in ("path", "circle", "rect", "line", "polyline", "polygon", "ellipse") for child in element):
            raise PublicationError("Markers may contain only simple publication shapes.")
        stack.extend((child, depth + 1, inside_definition or tag in ("defs", "marker")) for child in element)
    for element in root.iter():
        count += 1
        if count > MAX_ELEMENTS:
            raise PublicationError("SVG exceeds the 30000 element budget.")
        tag = _tag(element)
        if tag == "g" and element.get("data-edge-id"):
            rendered_edges.add(element.get("data-edge-id"))
        guide_id, owner = element.get("data-caption-guide-id"), element.get("data-caption-for-edge")
        if guide_id is not None or owner is not None:
            if tag != "path" or not guide_id or not owner or not ID.fullmatch(guide_id) or not ID.fullmatch(owner):
                raise PublicationError("Caption guides need paired valid local decoration and owner identities on a path.")
            if guide_id in caption_guides:
                raise PublicationError("Caption guide identities must be unique.")
            if element.get("pointer-events") != "none" or element.get("fill") != "none":
                raise PublicationError("Caption guides must be inert unfilled presentation paths.")
            if any(name.startswith("marker-") for name in element.attrib):
                raise PublicationError("Caption guides are unarrowed decorations, not tensor bindings.")
            caption_guides[guide_id] = owner
        elif element.get("pointer-events") is not None:
            raise PublicationError("Only identified caption-guide paths may use pointer-events.")
        text_size += len(element.text or "") + len(element.tail or "")
        if text_size > MAX_TEXT:
            raise PublicationError("SVG exceeds the text budget.")
        for attribute, value in element.attrib.items():
            if attribute not in COMMON | ATTRIBUTES[tag]:
                raise PublicationError(f"Unsupported publication attribute {tag}.{attribute}; external resources and executable content are forbidden.")
            if len(value) > (250_000 if attribute in ("d", "aria-label") else 4096):
                raise PublicationError(f"Attribute {tag}.{attribute} exceeds the size budget.")
            # No CSS or URL-bearing attributes are admitted. Marker URLs are
            # the single exception and must resolve to a local marker identity.
            if re.search(r"url\s*\(", value, flags=re.I) and attribute not in ("marker-end", "marker-start", "marker-mid"):
                raise PublicationError("CSS resource URLs are forbidden.")
            if attribute == "id":
                if not ID.fullmatch(value) or value in identifiers:
                    raise PublicationError("SVG identities must be unique valid local IDs.")
                identifiers.add(value)
                if tag == "marker":
                    markers.add(value)
            elif attribute == "data-edge-legend-id":
                if not ID.fullmatch(value):
                    raise PublicationError("Edge legend identities must be valid local IDs.")
            elif attribute in ("fill", "stroke"):
                if value not in ("none", "transparent", "currentColor") and not COLOR.fullmatch(value):
                    raise PublicationError(f"{tag}.{attribute} must be a hexadecimal color or none.")
            elif attribute in NUMERIC_ATTRIBUTES:
                _number(value, f"{tag}.{attribute}")
            elif attribute in ("width", "height"):
                numeric = re.sub(r"(?:mm|px|pt)$", "", value)
                if _number(numeric, f"{tag}.{attribute}") < 0:
                    raise PublicationError("SVG dimensions cannot be negative.")
            elif attribute == "viewBox":
                _numbers(value, f"{tag}.viewBox", 4)
            elif attribute == "stroke-dasharray":
                if value != "none":
                    _numbers(value, f"{tag}.stroke-dasharray")
            elif attribute == "points":
                numbers = _numbers(value, f"{tag}.points")
                if len(numbers) % 2:
                    raise PublicationError("SVG points require coordinate pairs.")
            elif attribute == "d":
                if not re.fullmatch(r"[MmLlHhVvCcSsQqTtAaZz0-9eE+.,\s-]*", value):
                    raise PublicationError("SVG path contains unsupported syntax.")
            elif attribute == "transform":
                remaining = re.sub(r"(?:matrix|translate|scale|rotate|skewX|skewY)\s*\(([-+0-9.eE,\s]+)\)", "", value).strip()
                if remaining:
                    raise PublicationError("SVG transform contains unsupported syntax.")
                for arguments in re.findall(r"\(([^)]+)\)", value):
                    _numbers(arguments, "transform")
            elif attribute.startswith("marker-") and attribute != "markerUnits":
                reference = LOCAL_URL.fullmatch(value)
                if not reference:
                    raise PublicationError("Marker references must be local fragment URLs.")
                references.append(reference.group(1))
            elif attribute in ENUMS:
                if value not in ENUMS[attribute]:
                    raise PublicationError(f"Unsupported {attribute} value.")
            elif attribute == "orient":
                if value not in ("auto", "auto-start-reverse"):
                    _number(value, "marker.orient")
            elif attribute == "font-family":
                fonts.add(value)
            elif attribute == "font-weight":
                if value not in ("normal", "bold"):
                    weight = _number(value, "font-weight")
                    if not 100 <= weight <= 900:
                        raise PublicationError("Font weight must be in 100–900.")
    if any(reference not in markers for reference in references):
        raise PublicationError("A marker reference is missing its local marker definition.")
    if any(owner not in rendered_edges for owner in caption_guides.values()):
        raise PublicationError("A caption guide owner is missing its rendered tensor edge.")
    if any(guide_id in identifiers or guide_id in rendered_edges for guide_id in caption_guides):
        raise PublicationError("Caption guide identities must be distinct from SVG and tensor edge identities.")
    return root, viewbox, sorted(fonts)


def _load_converter():
    try:
        converter = importlib.import_module("cairosvg")
        native = importlib.import_module("cairocffi")
        # Loading the shared Cairo library is part of actual capability evidence.
        native.cairo_version_string()
        paths = [str(Path(module.__file__).resolve()) for module in (converter, native)]
        if any("ArchCanvas_Model Architecture Studio_Temp" in path for path in paths):
            raise PublicationError("Publication dependency resolves to the failed prototype; select the formal project Python environment.")
        return converter, native
    except PublicationError:
        raise
    except (ImportError, OSError, AttributeError) as exc:
        raise PublicationError("PDF/PNG converter is unavailable. Install the publication extra into a project-local Python environment.") from exc


def capabilities() -> dict[str, Any]:
    receipt: dict[str, Any] = {
        "svg": True, "pdf": False, "png": False,
        "moduleOrigin": str(Path(__file__).resolve()),
        "pythonExecutable": str(Path(sys.executable).absolute()),
        "fontEmbeddingGuaranteed": False,
        "resourcePolicy": "self-contained-publication-svg; no external URLs, images, CSS, DTD or executable content",
    }
    try:
        converter, native = _load_converter()
        receipt.update({"pdf": True, "png": True, "converter": "CairoSVG", "converterVersion": converter.__version__, "converterOrigin": str(Path(converter.__file__).resolve()), "cairoVersion": native.cairo_version_string()})
    except PublicationError as exc:
        receipt["unavailableReason"] = str(exc)
    return receipt


def _no_fetch(url, resource_type):
    raise PublicationError("External resource access is forbidden during publication conversion.")


def _font_preflight(root: ET.Element, native) -> dict[str, Any]:
    """Check the same host Cairo font face used by CairoSVG for missing glyphs.

    This detects a known missing glyph before producing a misleading figure. It
    is a coverage check, not a shaping, family fidelity or embedding guarantee.
    """
    surface = native.ImageSurface(native.FORMAT_ARGB32, 1, 1)
    context = native.Context(surface)
    characters: dict[tuple[str, str], set[str]] = {}

    def text_run(text: str | None, font: str, weight: str):
        if text:
            characters.setdefault((font, weight), set()).update(character for character in text if not character.isspace())

    def visit(element, family="sans-serif", weight="normal", inside_text=False):
        family = element.get("font-family", family)
        weight = element.get("font-weight", weight)
        name = _tag(element)
        inside_text = inside_text or name in ("text", "tspan")
        if inside_text:
            text_run(element.text, family, weight)
        for child in element:
            visit(child, family, weight, inside_text)
            if inside_text:
                text_run(child.tail, family, weight)

    visit(root)
    reports = []
    missing = set()
    for (families, weight), chars in sorted(characters.items()):
        # CairoSVG text.py chooses only the first font-family token. Match that
        # choice exactly rather than certifying a fallback font it never uses.
        selected = families.split(",")[0].strip(" '\"")
        numeric_weight = int(weight) if weight.isdigit() else 700 if weight == "bold" else 400
        context.select_font_face(selected, native.FONT_SLANT_NORMAL, native.FONT_WEIGHT_BOLD if numeric_weight >= 550 else native.FONT_WEIGHT_NORMAL)
        context.set_font_size(12)
        face = context.get_scaled_font()
        absent = []
        for character in sorted(chars):
            glyphs = face.text_to_glyphs(0, 0, character, False)
            if not glyphs or any(glyph[0] == 0 for glyph in glyphs):
                absent.append(character)
                missing.add(character)
        reports.append({"requestedFamily": families, "selectedFamily": selected, "weight": weight, "checkedCharacters": len(chars), "missingCharacters": absent})
    surface.finish()
    if missing:
        preview = ", ".join(f"U+{ord(character):04X} ({character})" for character in sorted(missing)[:16])
        raise PublicationError(f"Host font preflight found missing glyphs: {preview}. Install the requested publication font or select a Scene font with coverage before exporting.")
    return {"status": "passed", "method": "Cairo scaled-font glyph coverage; same first requested family and weight as CairoSVG", "faces": reports, "shapingCertified": False}


def _pdf_dimensions(data: bytes) -> list[float]:
    if not data.startswith(b"%PDF-"):
        raise PublicationError("Converter did not produce a PDF artifact.")
    match = re.search(rb"/MediaBox\s*\[\s*([-+0-9.]+)\s+([-+0-9.]+)\s+([-+0-9.]+)\s+([-+0-9.]+)\s*\]", data)
    if not match:
        raise PublicationError("PDF page dimensions could not be verified.")
    box = [float(number) for number in match.groups()]
    return [box[2] - box[0], box[3] - box[1]]


def _png_density(data: bytes, dpi: int) -> tuple[bytes, int]:
    """Cairo emits pixels only; attach standard PNG physical-density metadata."""
    pixels_per_meter = round(dpi / 0.0254)
    body = b"pHYs" + struct.pack(">IIB", pixels_per_meter, pixels_per_meter, 1)
    density_chunk = struct.pack(">I", 9) + body + struct.pack(">I", zlib.crc32(body) & 0xffffffff)
    chunks = [data[:8]]
    cursor = 8
    inserted = False
    while cursor < len(data):
        if cursor + 12 > len(data):
            raise PublicationError("PNG chunk structure is incomplete.")
        length = struct.unpack(">I", data[cursor:cursor + 4])[0]
        end = cursor + length + 12
        if end > len(data):
            raise PublicationError("PNG chunk exceeds the artifact boundary.")
        kind = data[cursor + 4:cursor + 8]
        if kind == b"IDAT" and not inserted:
            chunks.append(density_chunk)
            inserted = True
        if kind != b"pHYs":
            chunks.append(data[cursor:end])
        cursor = end
    if not inserted:
        raise PublicationError("PNG is missing its image data.")
    return b"".join(chunks), pixels_per_meter


def export_svg(svg: str, format: str, width_mm: float = 180, dpi: int = 300) -> dict[str, Any]:
    """Convert a current-scene SVG with independently checked output geometry."""
    if format not in ("svg", "pdf", "png"):
        raise PublicationError("Export format must be svg, pdf or png.")
    if type(width_mm) not in (int, float) or not math.isfinite(width_mm) or not 25 <= width_mm <= 1000:
        raise PublicationError("Figure width must be finite and in 25–1000 mm.")
    if type(dpi) is not int or not 72 <= dpi <= 1200:
        raise PublicationError("DPI must be an integer in 72–1200.")
    root, viewbox, fonts = _validate(svg)
    height_mm = width_mm * viewbox[3] / viewbox[2]
    if height_mm > 5000:
        raise PublicationError("Figure height exceeds the 5000 mm budget.")
    root.set("width", f"{width_mm:.8g}mm")
    root.set("height", f"{height_mm:.8g}mm")
    validated_svg = ET.tostring(root, encoding="utf-8", xml_declaration=False)
    receipt: dict[str, Any] = {
        "format": format, "widthMm": float(width_mm), "heightMm": height_mm,
        "dpi": dpi, "inputSvgDigest": _hash(svg.encode("utf-8")), "svgDigest": _hash(validated_svg),
        "viewBox": list(viewbox), "geometryVerified": False,
        "fonts": {"requestedFamilies": fonts, "embeddingGuaranteed": False, "source": "host font resolution", "note": "SVG references font families. PNG rasterizes host-resolved fonts; PDF may subset fonts, but family fidelity and embedding are not certified."},
        "resources": "external access rejected", "publicationOrigin": str(Path(__file__).resolve()),
    }
    if format == "svg":
        data = validated_svg
        receipt["geometryVerified"] = True
    else:
        converter, native = _load_converter()
        receipt["fonts"]["glyphCoverage"] = _font_preflight(root, native)
        receipt.update({"converter": "CairoSVG", "converterVersion": converter.__version__, "converterOrigin": str(Path(converter.__file__).resolve()), "cairoVersion": native.cairo_version_string(), "pythonExecutable": str(Path(sys.executable).absolute())})
        try:
            if format == "png":
                width_px, height_px = round(width_mm / 25.4 * dpi), round(height_mm / 25.4 * dpi)
                if min(width_px, height_px) < 1 or max(width_px, height_px) > 30000 or width_px * height_px > MAX_PIXELS:
                    raise PublicationError("PNG exceeds the 40 megapixel / 30000 pixel side budget.")
                data = converter.surface.PNGSurface.convert(bytestring=validated_svg, dpi=dpi, output_width=width_px, output_height=height_px, unsafe=False, url_fetcher=_no_fetch)
                if not data.startswith(b"\x89PNG\r\n\x1a\n") or len(data) < 33:
                    raise PublicationError("Converter did not produce a PNG artifact.")
                dimensions = struct.unpack(">II", data[16:24])
                if dimensions != (width_px, height_px):
                    raise PublicationError("PNG output dimensions do not match requested physical width and DPI.")
                data, density = _png_density(data, dpi)
                receipt["pixelDimensions"] = list(dimensions)
                receipt["densityPixelsPerMeter"] = density
                receipt["densityDpi"] = density * 0.0254
            else:
                data = converter.surface.PDFSurface.convert(bytestring=validated_svg, dpi=96, unsafe=False, url_fetcher=_no_fetch)
                dimensions = _pdf_dimensions(data)
                expected = [width_mm / 25.4 * 72, height_mm / 25.4 * 72]
                if any(abs(actual - wanted) > 0.05 for actual, wanted in zip(dimensions, expected)):
                    raise PublicationError("PDF page size does not match the requested physical figure dimensions.")
                receipt["pageSizePt"] = dimensions
            receipt["geometryVerified"] = True
        except PublicationError:
            raise
        except (ValueError, TypeError, OSError, MemoryError) as exc:
            raise PublicationError(f"Publication conversion failed: {exc}") from exc
    receipt["outputDigest"] = _hash(data)
    receipt["bytes"] = len(data)
    return {"data": data, "mime": {"svg": "image/svg+xml", "pdf": "application/pdf", "png": "image/png"}[format], "extension": format, "receipt": receipt}
