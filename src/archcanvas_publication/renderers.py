from __future__ import annotations

import html
import json

from archcanvas_core.models import PublicationView, SceneNode, VisualScene, VisualSpec

from .label_layout import edge_label_placements


def _attribute(value: object) -> str:
    return html.escape(str(value), quote=True)


def _shape(node: SceneNode) -> str:
    bounds = node.bounds
    common = (
        f'class="node-shape shape-{node.shape}" fill="{_attribute(node.fill)}" '
        f'stroke="{_attribute(node.stroke)}" stroke-width="1.5"'
    )
    if node.shape == "merge":
        cx, cy = bounds.x + bounds.width / 2, bounds.y + bounds.height / 2
        points = " ".join(
            f"{x:.1f},{y:.1f}"
            for x, y in (
                (cx, bounds.y),
                (bounds.x + bounds.width, cy),
                (cx, bounds.y + bounds.height),
                (bounds.x, cy),
            )
        )
        return f'<polygon points="{points}" {common}/>'
    if node.shape in {"projection", "transform"}:
        inset = min(22.0, bounds.width * 0.12)
        points = " ".join(
            f"{x:.1f},{y:.1f}"
            for x, y in (
                (bounds.x + inset, bounds.y),
                (bounds.x + bounds.width, bounds.y),
                (bounds.x + bounds.width - inset, bounds.y + bounds.height),
                (bounds.x, bounds.y + bounds.height),
            )
        )
        return f'<polygon points="{points}" {common}/>'
    if node.shape == "condition":
        inset = min(28.0, bounds.width * 0.16)
        points = " ".join(
            f"{x:.1f},{y:.1f}"
            for x, y in (
                (bounds.x + inset, bounds.y),
                (bounds.x + bounds.width - inset, bounds.y),
                (bounds.x + bounds.width, bounds.y + bounds.height / 2),
                (bounds.x + bounds.width - inset, bounds.y + bounds.height),
                (bounds.x + inset, bounds.y + bounds.height),
                (bounds.x, bounds.y + bounds.height / 2),
            )
        )
        return f'<polygon points="{points}" {common}/>'
    if node.shape == "activation":
        return (
            f'<ellipse cx="{bounds.x + bounds.width / 2:.1f}" '
            f'cy="{bounds.y + bounds.height / 2:.1f}" rx="{bounds.width / 2:.1f}" '
            f'ry="{bounds.height / 2:.1f}" {common}/>'
        )
    if node.shape in {"tensor", "repeat"}:
        offset = 8.0
        return "".join(
            f'<rect class="{"node-shape" if step == 0 else "shape-detail"}" '
            f'x="{bounds.x + step:.1f}" y="{bounds.y - step:.1f}" '
            f'width="{bounds.width - offset:.1f}" height="{bounds.height:.1f}" rx="5" '
            f'fill="{_attribute(node.fill)}" stroke="{_attribute(node.stroke)}"/>'
            for step in (offset, offset / 2, 0.0)
        )
    if node.shape in {"normalization", "attention"}:
        outer = (
            f'<rect x="{bounds.x:.1f}" y="{bounds.y:.1f}" width="{bounds.width:.1f}" '
            f'height="{bounds.height:.1f}" rx="{18 if node.shape == "normalization" else 6}" {common}/>'
        )
        inner = (
            f'<rect class="shape-detail" x="{bounds.x + 6:.1f}" y="{bounds.y + 6:.1f}" '
            f'width="{bounds.width - 12:.1f}" height="{bounds.height - 12:.1f}" '
            f'rx="{13 if node.shape == "normalization" else 3}" fill="none" '
            f'stroke="{_attribute(node.stroke)}" stroke-width="1"/>'
        )
        return outer + inner
    radius = 28 if node.shape == "io" else 6 if node.shape != "container" else 3
    dash = ' stroke-dasharray="6 4"' if node.shape == "opaque" else ""
    return (
        f'<rect x="{bounds.x:.1f}" y="{bounds.y:.1f}" width="{bounds.width:.1f}" '
        f'height="{bounds.height:.1f}" rx="{radius}" {common}{dash}/>'
    )


def _node_svg(node: SceneNode) -> str:
    bounds = node.bounds
    canonical = " ".join(node.canonical_node_ids)
    evidence = " ".join(node.evidence_ids)
    classes = "scene-node root-container" if node.parent_scene_node_id is None else "scene-node"
    lines = [
        (
            f'<g id="{_attribute(node.scene_node_id)}" class="{classes}" tabindex="0" '
            f'data-view-node-id="{_attribute(node.view_node_id)}" '
            f'data-canonical-node-ids="{_attribute(canonical)}" '
            f'data-evidence-ids="{_attribute(evidence)}">'
        ),
        _shape(node),
    ]
    if node.parent_scene_node_id is None or (
        node.shape == "container" and not node.canonical_node_ids
    ):
        text_y = bounds.y + 24 if node.parent_scene_node_id is None else bounds.y - 8
        for index, label in enumerate(node.label_lines):
            lines.append(
                f'<text class="container-title" x="{bounds.x + 14:.1f}" '
                f'y="{text_y + index * 15:.1f}">{html.escape(label)}</text>'
            )
    else:
        line_height = 16
        secondary_height = 16 if node.secondary_label else 0
        block_height = len(node.label_lines) * line_height + secondary_height
        first_y = bounds.y + (bounds.height - block_height) / 2 + 13
        for index, label in enumerate(node.label_lines):
            lines.append(
                f'<text class="node-label" text-anchor="middle" '
                f'x="{bounds.x + bounds.width / 2:.1f}" '
                f'y="{first_y + index * line_height:.1f}">{html.escape(label)}</text>'
            )
        if node.secondary_label:
            secondary = node.secondary_label
            if len(secondary) > 28:
                secondary = secondary[:25] + "..."
            lines.append(
                f'<text class="node-secondary" text-anchor="middle" '
                f'x="{bounds.x + bounds.width / 2:.1f}" '
                f'y="{first_y + len(node.label_lines) * line_height + 1:.1f}">'
                f'{html.escape(secondary)}</text>'
            )
    lines.append("</g>")
    return "\n".join(lines)


def _edge_svg(scene: VisualScene) -> str:
    chunks: list[str] = []
    label_placements = edge_label_placements(scene)
    for edge in scene.edges:
        points = " ".join(f"{point.x:.1f},{point.y:.1f}" for point in edge.points)
        dash = f' stroke-dasharray="{_attribute(edge.dash)}"' if edge.dash else ""
        canonical = " ".join(edge.canonical_edge_ids)
        evidence = " ".join(edge.evidence_ids)
        portals = " ".join(edge.portal_ids)
        chunks.append(
            f'<g id="{_attribute(edge.scene_edge_id)}" class="scene-edge" '
            f'data-visual-relation="{_attribute(edge.visual_relation.value)}" '
            f'data-view-edge-id="{_attribute(edge.view_edge_id)}" '
            f'data-canonical-edge-ids="{_attribute(canonical)}" '
            f'data-source-port-id="{_attribute(edge.source_port_id or "")}" '
            f'data-target-port-id="{_attribute(edge.target_port_id or "")}" '
            f'data-evidence-ids="{_attribute(evidence)}" '
            f'data-portal-ids="{_attribute(portals)}" '
            f'data-route-digest="{_attribute(edge.route_digest or "")}" '
            f'data-source="{_attribute(edge.source_scene_node_id)}" '
            f'data-target="{_attribute(edge.target_scene_node_id)}">'
        )
        chunks.append(
            f'<polyline points="{points}" fill="none" stroke="{_attribute(edge.stroke)}" '
            f'stroke-width="{edge.width:.1f}"{dash} marker-end="url(#arrow)"/>'
        )
        if edge.visual_relation.value == "parallel-branch":
            start = edge.points[0]
            chunks.append(
                f'<circle class="edge-junction" cx="{start.x:.1f}" cy="{start.y:.1f}" '
                f'r="3.2" fill="{_attribute(edge.stroke)}"/>'
            )
        elif edge.visual_relation.value == "merge":
            end = edge.points[-1]
            chunks.append(
                f'<circle class="edge-junction" cx="{end.x:.1f}" cy="{end.y:.1f}" '
                f'r="3.2" fill="#fff" stroke="{_attribute(edge.stroke)}" stroke-width="1.5"/>'
            )
        placement = label_placements.get(edge.scene_edge_id)
        if placement:
            label = edge.label if len(edge.label) <= 28 else edge.label[:25] + "..."
            chunks.append(
                f'<text class="edge-label" text-anchor="middle" '
                f'x="{placement.x:.1f}" y="{placement.y:.1f}">'
                f'{html.escape(label)}</text>'
            )
        chunks.append("</g>")
    return "\n".join(chunks)


def _annotation_svg(scene: VisualScene) -> str:
    chunks: list[str] = []
    for annotation in scene.annotations:
        bounds = annotation.bounds
        chunks.extend(
            [
                (
                    f'<g id="{_attribute(annotation.annotation_id)}" class="scene-annotation" '
                    'role="note">'
                ),
                (
                    f'<rect x="{bounds.x:.1f}" y="{bounds.y:.1f}" '
                    f'width="{bounds.width:.1f}" height="{bounds.height:.1f}" rx="4" '
                    f'fill="{_attribute(annotation.fill)}" '
                    f'stroke="{_attribute(annotation.stroke)}" stroke-width="1.2"/>'
                ),
                (
                    f'<text x="{bounds.x + 10:.1f}" y="{bounds.y + 21:.1f}">'
                    f'{html.escape(annotation.text)}</text>'
                ),
                "</g>",
            ]
        )
    return "\n".join(chunks)


def _legend_svg(scene: VisualScene) -> str:
    if not scene.legend_placement or scene.legend_placement == "hidden" or not scene.edges:
        return ""
    entries = list(dict.fromkeys(edge.visual_relation.value for edge in scene.edges))
    width = max(116.0, max(len(item) for item in entries) * 7.0 + 38.0)
    height = len(entries) * 20.0 + 16.0
    left = scene.legend_placement.endswith("left")
    top = scene.legend_placement.startswith("top")
    x = 14.0 if left else scene.paper_width - width - 14.0
    y = 14.0 if top else scene.paper_height - height - 14.0
    chunks = [
        '<g class="scene-legend" role="list">',
        (
            f'<rect x="{x:.1f}" y="{y:.1f}" width="{width:.1f}" '
            f'height="{height:.1f}" rx="4" fill="#ffffff" fill-opacity="0.94" '
            'stroke="#c6cbd1"/>'
        ),
    ]
    edge_by_relation = {edge.visual_relation.value: edge for edge in scene.edges}
    for index, relation in enumerate(entries):
        edge = edge_by_relation[relation]
        row_y = y + 19.0 + index * 20.0
        dash = f' stroke-dasharray="{_attribute(edge.dash)}"' if edge.dash else ""
        chunks.append(
            f'<line x1="{x + 10:.1f}" y1="{row_y - 4:.1f}" '
            f'x2="{x + 30:.1f}" y2="{row_y - 4:.1f}" '
            f'stroke="{_attribute(edge.stroke)}" stroke-width="{edge.width:.1f}"{dash}/>'
        )
        chunks.append(
            f'<text x="{x + 36:.1f}" y="{row_y:.1f}">{html.escape(relation)}</text>'
        )
    chunks.append("</g>")
    return "\n".join(chunks)


def render_svg(scene: VisualScene) -> str:
    roots = [node for node in scene.nodes if node.parent_scene_node_id is None]
    containers = [
        node
        for node in scene.nodes
        if node.parent_scene_node_id is not None and node.shape == "container"
    ]
    children = [
        node
        for node in scene.nodes
        if node.parent_scene_node_id is not None and node.shape != "container"
    ]
    content = [
        '<?xml version="1.0" encoding="UTF-8"?>',
        (
            f'<svg xmlns="http://www.w3.org/2000/svg" role="img" '
            f'aria-labelledby="scene-title scene-desc" width="{scene.paper_width:.0f}" '
            f'height="{scene.paper_height:.0f}" '
            f'viewBox="0 0 {scene.paper_width:.1f} {scene.paper_height:.1f}" '
            f'data-scene-id="{_attribute(scene.scene_id)}" '
            f'data-view-id="{_attribute(scene.view_id)}" '
            f'data-layout-family="{_attribute(scene.layout_family)}">'
        ),
        f'<title id="scene-title">{html.escape(scene.view_id)}</title>',
        '<desc id="scene-desc">Canonical ArchCanvas publication scene.</desc>',
        "<defs>",
        (
            '<marker id="arrow" viewBox="0 0 10 10" refX="8.4" refY="5" '
            'markerWidth="5.5" markerHeight="5.5" orient="auto-start-reverse">'
        ),
        '<path d="M 0 0 L 10 5 L 0 10 z" fill="context-stroke"/>',
        "</marker>",
        "</defs>",
        '<style>.node-label,.container-title{font:600 13px Arial,Helvetica,sans-serif;fill:#182026;letter-spacing:0}.node-secondary{font:10px Arial,Helvetica,sans-serif;fill:#52606d;letter-spacing:0}.edge-label{font:10px Arial,Helvetica,sans-serif;fill:#36454f;paint-order:stroke;stroke:#fff;stroke-width:3px;stroke-linejoin:round;letter-spacing:0}.scene-annotation text,.scene-legend text{font:11px Arial,Helvetica,sans-serif;fill:#29323a;letter-spacing:0}.scene-caption{font:12px Arial,Helvetica,sans-serif;fill:#36454f;letter-spacing:0}.scene-node:focus{outline:none}</style>',
        f'<rect class="paper" width="{scene.paper_width:.1f}" height="{scene.paper_height:.1f}" fill="#ffffff"/>',
        '<g id="scene-root">',
        *(_node_svg(node) for node in roots),
        '<g class="container-layer">',
        *(_node_svg(node) for node in containers),
        "</g>",
        '<g class="edge-layer">',
        _edge_svg(scene),
        "</g>",
        '<g class="node-layer">',
        *(_node_svg(node) for node in children),
        "</g>",
        '<g class="annotation-layer">',
        _annotation_svg(scene),
        "</g>",
        _legend_svg(scene),
        (
            f'<text class="scene-caption" text-anchor="middle" '
            f'x="{scene.paper_width / 2:.1f}" y="{scene.paper_height - 12:.1f}">'
            f'{html.escape(scene.caption)}</text>'
            if scene.caption
            else ""
        ),
        "</g>",
        "</svg>",
    ]
    return "\n".join(content) + "\n"


def render_png(scene: VisualScene) -> bytes:
    """Rasterize the canonical SVG without introducing a second scene renderer."""
    import cairosvg

    return cairosvg.svg2png(
        bytestring=render_svg(scene).encode("utf-8"),
        output_width=round(scene.paper_width),
        output_height=round(scene.paper_height),
    )


def render_pdf(scene: VisualScene) -> bytes:
    """Convert the canonical SVG to a standalone single-page PDF."""
    import cairosvg

    return cairosvg.svg2pdf(bytestring=render_svg(scene).encode("utf-8"))


def render_html(scene: VisualScene, view: PublicationView, spec: VisualSpec) -> str:
    if scene.view_id != view.view_id or spec.view_id != view.view_id:
        raise ValueError("HTML inputs do not share a publication view")
    svg = render_svg(scene).removeprefix('<?xml version="1.0" encoding="UTF-8"?>\n')
    graph = {
        "scene": scene.model_dump(mode="json"),
        "view": view.model_dump(mode="json"),
        "spec": spec.model_dump(mode="json"),
    }
    graph_json = json.dumps(graph, ensure_ascii=False, separators=(",", ":")).replace(
        "</", "<\\/"
    )
    title = html.escape(f"ArchCanvas · {view.name}")
    return f"""<!doctype html>
<html lang="en">
<head>
<meta charset="utf-8">
<meta name="viewport" content="width=device-width,initial-scale=1">
<title>{title}</title>
<style>
:root{{--bg:#eef1f4;--panel:#fff;--border:#cbd2d9;--text:#17212b;--muted:#64707d;--accent:#1261a0;--toolbar:44px}}
*{{box-sizing:border-box}}html,body{{height:100%;margin:0}}body{{font:13px Arial,Helvetica,sans-serif;color:var(--text);background:var(--bg);letter-spacing:0;overflow:hidden}}
body.dark{{--bg:#171b20;--panel:#22282f;--border:#3f4852;--text:#edf1f5;--muted:#aab3bd;--accent:#69b3f0}}
.app{{height:100%;display:grid;grid-template-rows:var(--toolbar) 1fr;grid-template-columns:minmax(0,1fr) 280px}}
.toolbar{{grid-column:1/-1;display:flex;align-items:center;gap:6px;padding:5px 10px;background:var(--panel);border-bottom:1px solid var(--border);z-index:3}}
.brand{{font-weight:700;margin-right:8px;white-space:nowrap}}.view-name{{color:var(--muted);white-space:nowrap;margin-right:auto}}
button,input{{height:32px;border:1px solid var(--border);background:var(--panel);color:var(--text);font:inherit;border-radius:4px}}
button{{width:32px;padding:0;cursor:pointer;font-size:16px}}button:hover,button:focus-visible{{border-color:var(--accent);outline:2px solid color-mix(in srgb,var(--accent) 28%,transparent);outline-offset:1px}}
.search{{position:relative;width:min(280px,30vw)}}.search input{{width:100%;padding:0 30px 0 9px}}
.search button{{position:absolute;right:0;top:0;border:0;background:transparent}}
.viewport{{position:relative;min-width:0;min-height:0;overflow:hidden;cursor:grab;background:var(--bg)}}
.viewport.dragging{{cursor:grabbing}}.canvas{{width:100%;height:100%;display:block;touch-action:none}}
.inspector{{min-width:0;background:var(--panel);border-left:1px solid var(--border);padding:14px;overflow:auto}}
.inspector h2{{font-size:14px;margin:0 0 14px}}.field{{padding:9px 0;border-top:1px solid var(--border)}}.field b{{display:block;font-size:10px;text-transform:uppercase;color:var(--muted);margin-bottom:4px}}.field span{{overflow-wrap:anywhere}}
.empty{{color:var(--muted)}}.scene-node,.scene-edge{{transition:opacity .12s}}.scene-node.dim,.scene-edge.dim{{opacity:.12}}.scene-node.selected .node-shape{{stroke:#0069c2;stroke-width:3}}.scene-edge.selected polyline{{stroke-width:3.2}}
body.dark .canvas .paper{{fill:#f8fafc}}
@media(max-width:760px){{.app{{grid-template-columns:1fr}}.toolbar{{gap:4px;padding-inline:6px}}.brand{{font-size:0;margin-right:2px}}.brand::after{{content:'AC';font-size:13px}}.toolbar>button{{width:28px}}.inspector{{position:absolute;right:8px;bottom:8px;width:min(280px,calc(100vw - 16px));max-height:42vh;border:1px solid var(--border);z-index:2}}.view-name{{display:none}}.search{{width:92px;min-width:92px}}}}
</style>
</head>
<body>
<main class="app">
  <header class="toolbar">
    <div class="brand">ArchCanvas</div><div class="view-name">Depth {view.visible_depth}/{view.max_depth} · {html.escape(view.name)}</div>
    <div class="search"><input id="search" type="search" aria-label="Search architecture" placeholder="Search"><button id="search-go" title="Search" aria-label="Search">⌕</button></div>
    <button id="upstream" title="Show upstream" aria-label="Show upstream">←</button>
    <button id="downstream" title="Show downstream" aria-label="Show downstream">→</button>
    <button id="zoom-out" title="Zoom out" aria-label="Zoom out">−</button>
    <button id="zoom-in" title="Zoom in" aria-label="Zoom in">+</button>
    <button id="reset" title="Fit scene" aria-label="Fit scene">⌂</button>
    <button id="theme" title="Toggle theme" aria-label="Toggle theme">◐</button>
  </header>
  <section class="viewport" id="viewport" aria-label="Architecture canvas">{svg}</section>
  <aside class="inspector" aria-live="polite"><h2>Inspector</h2><div id="details" class="empty">No selection</div></aside>
</main>
<script id="archcanvas-data" type="application/json">{graph_json}</script>
<script>
(()=>{{
const data=JSON.parse(document.getElementById('archcanvas-data').textContent),svg=document.querySelector('.canvas,svg'),viewport=document.getElementById('viewport'),details=document.getElementById('details');
svg.classList.add('canvas');const base=[0,0,data.scene.paper_width,data.scene.paper_height];let box=base.slice(),drag=null,selected=null;
const nodes=new Map(data.scene.nodes.map(n=>[n.scene_node_id,n])),edges=data.scene.edges;
const applyBox=()=>svg.setAttribute('viewBox',box.join(' '));
function zoom(f,cx=box[0]+box[2]/2,cy=box[1]+box[3]/2){{const nw=box[2]*f,nh=box[3]*f;box=[cx-(cx-box[0])*f,cy-(cy-box[1])*f,nw,nh];applyBox()}}
function clear(){{document.querySelectorAll('.scene-node,.scene-edge').forEach(e=>e.classList.remove('dim','selected'))}}
function reach(direction){{if(!selected)return;const seen=new Set([selected]),queue=[selected];while(queue.length){{const id=queue.shift();for(const e of edges){{const a=direction==='up'?e.target_scene_node_id:e.source_scene_node_id,b=direction==='up'?e.source_scene_node_id:e.target_scene_node_id;if(a===id&&!seen.has(b)){{seen.add(b);queue.push(b)}}}}}}clear();document.querySelectorAll('.scene-node').forEach(e=>{{if(!seen.has(e.id))e.classList.add('dim')}});document.querySelectorAll('.scene-edge').forEach(el=>{{const e=edges.find(x=>x.scene_edge_id===el.id);if(!e||!seen.has(e.source_scene_node_id)||!seen.has(e.target_scene_node_id))el.classList.add('dim');else el.classList.add('selected')}})}}
function select(id){{const n=nodes.get(id);if(!n)return;selected=id;clear();document.getElementById(id)?.classList.add('selected');const view=data.view.nodes.find(x=>x.view_node_id===n.view_node_id);details.innerHTML=`<div class="field"><b>Name</b><span>${{escapeHtml(view?.semantic_name||id)}}</span></div><div class="field"><b>Canonical IDs</b><span>${{n.canonical_node_ids.map(escapeHtml).join('<br>')}}</span></div><div class="field"><b>Evidence</b><span>${{n.evidence_ids.length?n.evidence_ids.map(escapeHtml).join('<br>'):'None'}}</span></div><div class="field"><b>Glyph</b><span>${{escapeHtml(n.shape)}}</span></div>`}}
function escapeHtml(v){{const d=document.createElement('div');d.textContent=v;return d.innerHTML}}
document.querySelectorAll('.scene-node:not(.root-container)').forEach(el=>{{el.addEventListener('click',e=>{{e.stopPropagation();select(el.id)}});el.addEventListener('keydown',e=>{{if(e.key==='Enter'||e.key===' ')select(el.id)}})}});
document.getElementById('search-go').onclick=()=>{{const q=document.getElementById('search').value.trim().toLowerCase();if(!q)return;const n=data.scene.nodes.find(n=>[n.scene_node_id,n.view_node_id,...n.canonical_node_ids].join(' ').toLowerCase().includes(q));if(n)select(n.scene_node_id)}};
document.getElementById('search').addEventListener('keydown',e=>{{if(e.key==='Enter')document.getElementById('search-go').click()}});
document.getElementById('zoom-in').onclick=()=>zoom(.8);document.getElementById('zoom-out').onclick=()=>zoom(1.25);document.getElementById('reset').onclick=()=>{{box=base.slice();applyBox();clear()}};document.getElementById('theme').onclick=()=>document.body.classList.toggle('dark');document.getElementById('upstream').onclick=()=>reach('up');document.getElementById('downstream').onclick=()=>reach('down');
svg.addEventListener('wheel',e=>{{e.preventDefault();zoom(e.deltaY>0?1.12:.89)}},{{passive:false}});svg.addEventListener('pointerdown',e=>{{if(e.target.closest('.scene-node'))return;drag=[e.clientX,e.clientY,...box];viewport.classList.add('dragging');svg.setPointerCapture(e.pointerId)}});svg.addEventListener('pointermove',e=>{{if(!drag)return;const sx=box[2]/svg.clientWidth,sy=box[3]/svg.clientHeight;box[0]=drag[2]-(e.clientX-drag[0])*sx;box[1]=drag[3]-(e.clientY-drag[1])*sy;applyBox()}});svg.addEventListener('pointerup',()=>{{drag=null;viewport.classList.remove('dragging')}});viewport.addEventListener('click',e=>{{if(e.target===svg||e.target.classList.contains('paper')){{selected=null;clear();details.textContent='No selection';details.className='empty'}}}});
applyBox();
}})();
</script>
</body>
</html>
"""
