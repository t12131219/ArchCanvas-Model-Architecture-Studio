#!/usr/bin/env python3
"""Verify saved explicit LSTM geometry; never import or execute model code."""
from __future__ import annotations
import argparse
import copy
import hashlib
import json
import math
import sys
from pathlib import Path

HERE = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(HERE))
from layout import nearest_visible, validate
from verify import exported_view


def digest(path):
    return hashlib.sha256(Path(path).read_bytes()).hexdigest()


def run():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--out', type=Path, default=HERE / 'generated/lstmcell_geometry_review.json')
    args = parser.parse_args()
    folder = HERE / 'generated/lstmcell'
    ir = json.loads((folder / 'semantic_ir.json').read_text())
    evidence = json.loads((folder / 'source_evidence.json').read_text())
    parents = {n['id']: n['parent'] for n in ir['nodes']}
    views = []
    detailed = None
    for index, view in enumerate(['overview', 'modules', 'detailed'], 1):
        layout_path = folder / f'layout_{view}.json'
        svg_path = folder / f'figure{index}_{view}.svg'
        layout = json.loads(layout_path.read_text())
        export = exported_view(svg_path, layout, evidence, ir, png=True)
        assert all(r.get('semantic_src') for r in layout['routes']), 'invented unbound graph bus'
        expected = set()
        for edge in ir['edges']:
            src = nearest_visible(edge['src'], parents, layout['ports'])
            dst = nearest_visible(edge['dst'], parents, layout['ports'])
            if src is not None and dst is not None and src != dst:
                expected.add(tuple(edge[k] for k in ['src', 'dst', 'src_port', 'dst_port', 'role']))
        actual = set()
        for route in layout['routes']:
            actual.add(tuple(route['semantic_' + k] for k in ['src', 'dst', 'src_port', 'dst_port']) + (route['role'],))
            assert route['projected_src'] == nearest_visible(route['semantic_src'], parents, layout['ports'])
            assert route['projected_dst'] == nearest_visible(route['semantic_dst'], parents, layout['ports'])
            assert route.get('minimum_terminal') == 24
            assert route.get('frame_clearance') == 8
            assert math.dist(route['points'][0], route['points'][1]) >= 24 - 1e-6
            assert math.dist(route['points'][-2], route['points'][-1]) >= 24 - 1e-6
        assert expected == actual, 'visible explicit dependencies differ from canonical IR'
        for t in range(3):
            assert layout['ports'][f'lstmcell.x{t}']['in'][0] == layout['ports'][f'lstmcell.step{t}']['in'][0]
        for t in [0, 1]:
            state_routes = [r for r in layout['routes'] if r['role'] == 'recurrent_state'
                            and r['semantic_src'].startswith(f'lstmcell.step{t}.')]
            assert len(state_routes) == 2
            assert state_routes[0]['src'] != state_routes[1]['src'], 'hidden and cell use same geometric port'
            assert state_routes[0]['dst'] != state_routes[1]['dst'], 'hidden and cell merge at destination'
        views.append(dict(view=view,canvas=layout['canvas'],
                          svg_sha256=digest(svg_path),png_sha256=digest(svg_path.with_suffix('.png')),
                          layout_sha256=digest(layout_path),checks=export,
                          explicit_dependencies=len(actual),source_and_terminal_stubs='>=24px',
                          parallel_frame_border_clearance='>=8px; perpendicular crossings allowed',
                          time_token_alignment='all three tokens align with their own cell',
                          state_projection='hidden and cell retain distinct geometric ports'))
        if view == 'detailed':detailed = layout

    negatives = []
    node = 'lstmcell.unbind';port = 'out.aux0'
    box = next(b for b in detailed['boxes'] if b['id'] == node)
    x,y,w,h = box['bbox']
    for name, mutate in [
        ('top port moved 1px into actual rectangle',lambda d:d['ports'][node][port].__setitem__(1,y+1)),
        ('top port moved to 4px corner clearance',lambda d:d['ports'][node][port].__setitem__(0,x+4)),
        ('malformed auxiliary port name',lambda d:d['ports'][node].__setitem__('out.auxoops',d['ports'][node][port])),
    ]:
        bad = copy.deepcopy(detailed);mutate(bad)
        try:exported_view(folder/'figure3_detailed.svg',bad,evidence,ir)
        except ValueError as exc:negatives.append(dict(case=name,rejected=True,reason=str(exc)))
        else:raise AssertionError('Invalid geometric port was accepted: '+name)

    # Keep two real canonical gate-slice bindings, but deliberately give them
    # the very same physical wire. Endpoints stay registered so the specific
    # distinct-source-port overlap rule must reject the mutation.
    bad = copy.deepcopy(detailed)
    gates = [r for r in bad['routes'] if r.get('semantic_src') == 'lstmcell.step1.chunk']
    first = next(r for r in gates if r['semantic_src_port'] == 'item[0]')
    second = next(r for r in gates if r['semantic_src_port'] == 'item[1]')
    for key in ['points','src','dst','projected_src','projected_dst']:
        second[key] = copy.deepcopy(first[key])
    failure = validate(bad)
    reasons = [error for error in failure['errors'] if error.startswith('distinct tensor routes share a segment:')]
    assert not failure['passed'] and reasons, 'distinct chunk item[0]/item[1] were treated as one tensor'
    negatives.append(dict(case='two different canonical chunk slices forced onto one registered geometric wire',
                          rejected=True,reason=reasons))

    bad = copy.deepcopy(detailed)
    bypass = next(r for r in bad['routes'] if r['semantic_src'] == 'lstmcell.step1.o'
                  and r['semantic_dst'] == 'lstmcell.step1.hy')
    frame = next(b for b in bad['boxes'] if b['id'] == 'lstmcell.step1.cell_update')
    x,y,w,h = frame['bbox'];a = bypass['points'][0];b = bypass['points'][-1]
    lane = x+w+4
    bypass['points'] = [a,[a[0],a[1]-24],[a[0],y+h+12],[lane,y+h+12],
                        [lane,y-12],[b[0],y-12],[b[0],b[1]+24],b]
    failure = validate(bad)
    reasons = [error for error in failure['errors'] if error.startswith('explicit route too close to frame border:')]
    assert not failure['passed'] and reasons, 'parallel graph wire 4px from frame border was accepted'
    negatives.append(dict(case='output-gate bypass forced 4px beside Cell state update frame',
                          rejected=True,reason=reasons))

    report = dict(status='PASS',scope='saved LSTM SVG/XML, geometry and canonical projection; no model execution',
                  files={name:digest(HERE/name) for name in ['spec.py','evidence.py','layout.py','verify.py',
                                                           'adapters/lstmcell.py','checks/lstmcell_geometry.py']},
                  semantic_ir_sha256=digest(folder/'semantic_ir.json'),source_evidence_sha256=digest(folder/'source_evidence.json'),
                  views=views,negative_geometry_checks=negatives)
    args.out.parent.mkdir(parents=True,exist_ok=True)
    args.out.write_text(json.dumps(report,ensure_ascii=False,indent=2)+'\n')
    print(json.dumps(dict(status='PASS',views=len(views),negative_cases=len(negatives),out=str(args.out))))


if __name__ == '__main__':run()
