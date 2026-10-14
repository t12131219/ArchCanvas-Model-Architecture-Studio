#!/usr/bin/env python3
"""Read-only SVG+layout diagnostics for Transformer diagrams (stdlib only).

Checks rendered paths, including paths omitted from layout.routes. Border overlap
means a nonzero straight segment runs along a rectangle's straight border, not a
normal orthogonal crossing at a port. Rectangles entirely containing a path are
not treated as obstacles; containment alone never creates a finding.
"""
from __future__ import annotations
import argparse
import json
import math
import re
import xml.etree.ElementTree as ET
from pathlib import Path

NUM = r'[-+]?(?:\d*\.\d+|\d+\.?\d*)(?:[eE][-+]?\d+)?'
EPS = 1e-5

def parse_path(d):
    """Parse the generated absolute/relative M L H V subset; ignore fill paths."""
    tokens = re.findall(r'[a-zA-Z]|' + NUM, d)
    points, pos, cmd, i = [], (0., 0.), None, 0
    while i < len(tokens):
        if tokens[i].isalpha():
            cmd = tokens[i]
            i += 1
        if cmd is None or cmd.upper() not in ('M', 'L', 'H', 'V'):
            return None
        absolute = cmd.isupper()
        if cmd.upper() in ('M', 'L'):
            if i + 1 >= len(tokens) or tokens[i].isalpha() or tokens[i+1].isalpha():
                return None
            a, b = float(tokens[i]), float(tokens[i+1])
            i += 2
            pos = (a, b) if absolute else (pos[0]+a, pos[1]+b)
            if cmd.upper() == 'M':
                cmd = 'L' if absolute else 'l'
        elif cmd.upper() == 'H':
            a = float(tokens[i]); i += 1
            pos = (a if absolute else pos[0]+a, pos[1])
        else:
            b = float(tokens[i]); i += 1
            pos = (pos[0], b if absolute else pos[1]+b)
        if not points or dist(points[-1], pos) > EPS:
            points.append(pos)
    return points

def dist(a, b):
    return math.hypot(a[0]-b[0], a[1]-b[1])

def last_straight_length(points):
    """Merge redundant collinear points before finding the final approach length."""
    nonzero = [(a,b) for a,b in zip(points, points[1:]) if dist(a,b)>EPS]
    if not nonzero:
        return 0.
    end = nonzero[-1][1]
    start = nonzero[-1][0]
    direction = (end[0]-start[0],end[1]-start[1])
    for a,b in reversed(nonzero[:-1]):
        vector=(b[0]-a[0],b[1]-a[1])
        if abs(direction[0]*vector[1]-direction[1]*vector[0])>EPS or direction[0]*vector[0]+direction[1]*vector[1]<0:
            break
        start=a
    return dist(start,end)

def rect_overlap(a,b,rect):
    """Return (side,length) for overlap with actual straight rounded-rect borders."""
    x,y,w,h=rect['bbox']; rx=min(rect.get('rx',0),w/2,h/2)
    if abs(a[1]-b[1])<EPS:
        side='top' if abs(a[1]-y)<EPS else 'bottom' if abs(a[1]-y-h)<EPS else None
        if side:
            length=min(max(a[0],b[0]),x+w-rx)-max(min(a[0],b[0]),x+rx)
            if length>EPS: return side,length
    if abs(a[0]-b[0])<EPS:
        side='left' if abs(a[0]-x)<EPS else 'right' if abs(a[0]-x-w)<EPS else None
        if side:
            length=min(max(a[1],b[1]),y+h-rx)-max(min(a[1],b[1]),y+rx)
            if length>EPS: return side,length
    return None

def numeric_attr(e,key,default=0):
    raw=e.get(key,str(default))
    return float(raw) if re.fullmatch(NUM,raw) else None

def diagnose(svg_path, threshold=18., border_threshold=18.):
    tree=ET.parse(svg_path)
    rects, paths=[],[]
    def walk(el,in_defs=False):
        tag=el.tag.rsplit('}',1)[-1]
        in_defs=in_defs or tag=='defs'
        if not in_defs and tag=='rect' and float(el.get('stroke-width','0')) >= 1:
            bbox=[numeric_attr(el,k) for k in ('x','y','width','height')]
            if all(v is not None for v in bbox):
                rects.append(dict(id=el.get('data-node-id',f'rect@{bbox[0]:g},{bbox[1]:g}'),bbox=bbox,rx=numeric_attr(el,'rx') or 0))
        if not in_defs and tag=='path' and el.get('fill')=='none':
            points=parse_path(el.get('d',''))
            if points and len(points)>1:
                paths.append(dict(points=points,arrow=bool(el.get('marker-end')),id=el.get('data-route-id') or el.get('id') or f'path#{len(paths)+1}'))
        for child in el:
            walk(child,in_defs)
    walk(tree.getroot())
    # Add recorded route names by identical geometry; raw SVG is still authoritative.
    layout_path=svg_path.with_name('layout_'+{'figure1_overview':'overview','figure2_modules':'modules','figure3_detailed':'detailed'}.get(svg_path.stem,svg_path.stem)+'.json')
    layout=json.loads(layout_path.read_text()) if layout_path.exists() else None
    if layout:
        for p in paths:
            for r in layout['routes']:
                if len(p['points'])==len(r['points']) and all(dist(a,b)<EPS for a,b in zip(p['points'],r['points'])):
                    p['id']=r['id']; break
    shorts,borders=[],[]
    for p in paths:
        if p['arrow']:
            length=last_straight_length(p['points'])
            if length < threshold-EPS:
                shorts.append(dict(route=p['id'],length=round(length,3),elbow=len(p['points'])>2,points=p['points']))
        for seg,(a,b) in enumerate(zip(p['points'],p['points'][1:])):
            for rect in rects:
                hit=rect_overlap(a,b,rect)
                if hit and hit[1]>=border_threshold-EPS:
                    borders.append(dict(route=p['id'],segment=seg,rect=rect['id'],side=hit[0],length=round(hit[1],3),a=a,b=b))
    endpoint_errors=[]
    endpoint_unregistered=[]
    if layout:
        ports=layout.get('ports',{})
        aliases={'input':'in','in_':'in'}
        for r in layout['routes']:
            for end,point in [('src',r['points'][0]),('dst',r['points'][-1])]:
                ref=r.get(end)
                if not ref: continue
                name,sep,port=ref.partition(':')
                port=aliases.get(port,port) if sep else ('out' if end=='src' else 'in')
                if name not in ports or port not in ports[name]:
                    endpoint_unregistered.append(dict(route=r['id'],end=end,ref=ref))
                if name in ports and port in ports[name]:
                    expected=ports[name][port]
                    if dist(point,expected)>EPS:
                        endpoint_errors.append(dict(route=r['id'],end=end,ref=ref,actual=point,expected=expected))
    return dict(svg=str(svg_path),path_count=len(paths),rect_count=len(rects),threshold=threshold,short_terminal=shorts,border_collinear=borders,endpoint_errors=endpoint_errors,endpoint_unregistered=endpoint_unregistered)

def main():
    ap=argparse.ArgumentParser(description=__doc__)
    ap.add_argument('paths',nargs='+',type=Path)
    ap.add_argument('--terminal',type=float,default=18)
    ap.add_argument('--border',type=float,default=18)
    ap.add_argument('--summary',action='store_true')
    args=ap.parse_args()
    output=[]
    for path in args.paths:
        paths=sorted(path.glob('figure*.svg')) if path.is_dir() else [path]
        for svg in paths:
            data=diagnose(svg,args.terminal,args.border)
            if args.summary:
                data={k:v for k,v in data.items() if k not in ('short_terminal','border_collinear','endpoint_errors','endpoint_unregistered')} | {k:len(data[k]) for k in ('short_terminal','border_collinear','endpoint_errors','endpoint_unregistered')}
            output.append(data)
    print(json.dumps(output,ensure_ascii=False,indent=2))

if __name__=='__main__':
    main()
