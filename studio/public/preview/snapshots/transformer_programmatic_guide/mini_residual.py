from dataclasses import dataclass
from pathlib import Path
from html import escape
import json


@dataclass
class Box:
    x: float
    y: float
    w: float
    h: float

    def port(self, side):
        return {
            'in': (self.x + self.w / 2, self.y + self.h),
            'out': (self.x + self.w / 2, self.y),
            'skip': (self.x, self.y + self.h / 2),
        }[side]


# Teaching annotation: F and Add&Norm are compound glyphs, not runtime traces.
# Dimensions are measured from the child chain, including a real input glyph.
u = 8
pad, gap, lane = 3*u, 3*u, 4*u
norm_h, sub_h, input_h, core_w = 7*u, 17*u, 5*u, 45*u
margin = 4*u
parent = Box(margin, margin, 2*pad + lane + core_w,
             2*pad + norm_h + 2*gap + sub_h + input_h)
core_x = parent.x + pad + lane
norm = Box(core_x, parent.y + pad, core_w, norm_h)
sub = Box(core_x, norm.y + norm.h + gap, core_w, sub_h)
x_input = Box(core_x + (core_w - 15*u)/2, sub.y + sub.h + gap, 15*u, input_h)
W, H = parent.x + parent.w + margin, parent.y + parent.h + margin
nodes = {'input_x': x_input, 'F': sub, 'add_norm': norm}
ports = {identity: {name: list(box.port(name)) for name in ('in', 'out', 'skip')}
         for identity, box in nodes.items()}
elements, routes = [], []


def rect(identity, b, color):
    elements.append(
        f'<g data-node-id="{identity}"><rect x="{b.x}" y="{b.y}" '
        f'width="{b.w}" height="{b.h}" rx="12" fill="{color}" '
        f'stroke="#263348" stroke-width="2"/></g>')


def label(x, y, text, size=18):
    elements.append(
        f'<text x="{x}" y="{y}" text-anchor="middle" '
        f'font-family="DejaVu Sans,sans-serif" font-size="{size}" '
        f'fill="#172336">{escape(text)}</text>')


def edge(identity, src, dst, points, role):
    src_node, src_port = src.split(':')
    dst_node, dst_port = dst.split(':')
    assert list(points[0]) == ports[src_node][src_port]
    assert list(points[-1]) == ports[dst_node][dst_port]
    a, b = points[-2:]
    assert abs(b[0]-a[0]) + abs(b[1]-a[1]) >= 18
    assert all(p[0] == q[0] or p[1] == q[1] for p, q in zip(points, points[1:]))
    record = dict(id=identity, src=src, dst=dst, role=role,
                  points=[list(p) for p in points], arrow=True)
    routes.append(record)
    data = 'M ' + ' L '.join(f'{x},{y}' for x, y in points)
    elements.append(
        f'<path data-route-id="{identity}" data-src="{src}" data-dst="{dst}" '
        f'data-role="{role}" d="{data}" fill="none" stroke="#263348" '
        f'stroke-width="2" stroke-linejoin="round" marker-end="url(#arrow)"/>')


rect('residual_scope', parent, '#e5f3fc')
rect('add_norm', norm, '#fff6bf')
rect('F', sub, '#ffddb8')
rect('input_x', x_input, '#f4cee3')
label(norm.x + norm.w/2, norm.y + 24, 'Add & Norm (Post-LN)')
label(norm.x + norm.w/2, norm.y + 44, 'z = LN(x + Dropout(F(x)))', 14)
label(sub.x + sub.w/2, sub.y + sub.h/2, 'F(x): attention or FFN')
label(x_input.x + x_input.w/2, x_input.y + 26, 'Input x', 16)

# Both inputs are explicit: transformed F.out and unchanged input_x.out.
# The skip branch shares only the original x trunk; it never starts at F.out.
edge('main-F-to-norm', 'F:out', 'add_norm:in', [sub.port('out'), norm.port('in')], 'transformed_value')
edge('input-to-F', 'input_x:out', 'F:in', [x_input.port('out'), sub.port('in')], 'tensor')
sx, sy = x_input.port('out')
lx, ly = norm.port('skip')
skip_x = core_x - lane
tap_y = sy - gap/2
edge('retained-x-to-norm', 'input_x:out', 'add_norm:skip',
     [(sx, sy), (sx, tap_y), (skip_x, tap_y), (skip_x, ly), (lx, ly)], 'retained_input')
elements.append(f'<circle cx="{sx}" cy="{tap_y}" r="2.5" fill="#263348"/>')
label(skip_x - 10, (tap_y + ly)/2, 'x', 16)
annotation = dict(schema='residual-teaching-annotation/1',
                  kind='teaching annotation; not a concrete model analysis or execution',
                  equation='z = LN(x + Dropout(F(x)))', computation_direction='bottom-to-top',
                  minimum_terminal=18, canvas=[W, H],
                  boxes={name: [box.x, box.y, box.w, box.h] for name, box in nodes.items()},
                  ports=ports, routes=routes,
                  contracts={'main': ['F:out', 'add_norm:in'],
                             'input': ['input_x:out', 'F:in'],
                             'residual': ['input_x:out', 'add_norm:skip']})
svg = f'''<svg xmlns="http://www.w3.org/2000/svg" width="{W}" height="{H}" viewBox="0 0 {W} {H}">
<metadata id="annotation-contract">{escape(json.dumps(annotation, ensure_ascii=False))}</metadata>
<defs><marker id="arrow" markerUnits="userSpaceOnUse" markerWidth="10" markerHeight="8" refX="9" refY="4"
orient="auto"><path d="M0,0 L9,4 L0,8 Z" fill="#263348"/></marker></defs>
<rect width="100%" height="100%" fill="white"/>
{''.join(elements)}</svg>'''
folder = Path(__file__).resolve().parent
(folder/'mini_residual.svg').write_text(svg, encoding='utf-8')
(folder/'mini_residual_layout.json').write_text(json.dumps(annotation, ensure_ascii=False, indent=2)+'\n', encoding='utf-8')
