from dataclasses import dataclass
from pathlib import Path
from html import escape

@dataclass
class Box:
    x: float
    y: float
    w: float
    h: float

    def port(self, side):
        return {
            "in": (self.x + self.w / 2, self.y + self.h),
            "out": (self.x + self.w / 2, self.y),
            "left": (self.x, self.y + self.h / 2),
        }[side]

u = 8
pad, gap, lane = 3*u, 3*u, 4*u
norm_h, sub_h, core_w = 7*u, 17*u, 45*u
margin = 4*u

# 先测量父容器，再摆放子容器；不是给每个图元分别手填坐标。
parent = Box(margin, margin,
             2*pad + lane + core_w,
             2*pad + norm_h + gap + sub_h)
core_x = parent.x + pad + lane
norm = Box(core_x, parent.y + pad, core_w, norm_h)
sub = Box(core_x, norm.y + norm.h + gap, core_w, sub_h)

elements = []
def rect(b, color):
    elements.append(
        f'<rect x="{b.x}" y="{b.y}" width="{b.w}" height="{b.h}" '
        f'rx="12" fill="{color}" stroke="#17212b" stroke-width="2"/>')

def label(x, y, s, size=18):
    elements.append(
        f'<text x="{x}" y="{y}" text-anchor="middle" '
        f'font-family="DejaVu Sans,sans-serif" font-size="{size}">{escape(s)}</text>')

def edge(points):
    data = " ".join(f"{x},{y}" for x, y in points)
    elements.append(
        f'<polyline points="{data}" fill="none" stroke="#17212b" '
        f'stroke-width="2" marker-end="url(#arrow)"/>')

rect(parent, "#e5f3fc")
rect(norm, "#fff6bf")
rect(sub, "#ffddb8")
label(norm.x + norm.w/2, norm.y + 24, "Add & Norm (Post-LN)")
label(norm.x + norm.w/2, norm.y + 44, "z = LN(x + Dropout(F(x)))", 14)
label(sub.x + sub.w/2, sub.y + sub.h/2, "F(x): attention or FFN")

# 主边来自F的输出，旁路来自F的输入；两者进入复合图元的不同端口。
edge([sub.port("out"), norm.port("in")])
sx, sy = sub.port("in")
lx, ly = norm.port("left")
skip_x = core_x - lane
edge([(sx, sy), (sx, sy + gap/3),
      (skip_x, sy + gap/3), (skip_x, ly), (lx, ly)])
label(skip_x - 10, (sy+ly)/2, "x", 16)
W, H = parent.x + parent.w + margin, parent.y + parent.h + margin
svg = f'''<svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 {W} {H}">
<defs><marker id="arrow" markerWidth="8" markerHeight="8" refX="7" refY="4"
orient="auto"><path d="M0,0 L8,4 L0,8 Z" fill="#17212b"/></marker></defs>
<rect width="100%" height="100%" fill="white"/>
{"".join(elements)}</svg>'''
Path("mini_residual.svg").write_text(svg, encoding="utf-8")
