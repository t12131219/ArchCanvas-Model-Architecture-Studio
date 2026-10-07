"""Independent, bounded geometry facts from exported publication SVG, not a routing oracle."""
import hashlib
import itertools
import json
from pathlib import Path
import re
import sys
import xml.etree.ElementTree as ET

formal = Path.cwd()
case = sys.argv[1]
source = formal / 'docs/evidence/m4-monochrome-role-work/browser-current' / case / 'figure.svg'
output = formal / 'docs/evidence/m4-monochrome-role-work/pixel-review-attempt-1' / case / 'actual-route-observation.json'
raw = source.read_bytes()
root = ET.fromstring(raw)
metadata = json.loads(root.find('{http://www.w3.org/2000/svg}metadata').text)
facts = {b['sceneEdgeId']: b for b in metadata['renderedBindings']}


def segments(d):
    parts = re.findall(r'[MVH]|-?\d+(?:\.\d+)?', d)
    result = []
    x = y = 0
    index = 0
    while index < len(parts):
        command = parts[index]
        index += 1
        if command == 'M':
            x, y = float(parts[index]), float(parts[index + 1])
            index += 2
        elif command in ['H', 'V']:
            nx, ny = (float(parts[index]), y) if command == 'H' else (x, float(parts[index]))
            index += 1
            if nx != x or ny != y:
                result.append({'a': [x, y], 'b': [nx, ny], 'axis': command})
            x, y = nx, ny
        else:
            raise ValueError(f'Unexpected route token {command}')
    return result


edges = []
for element in root.iter():
    if 'data-edge-id' not in element.attrib:
        continue
    edge_id = element.attrib['data-edge-id']
    visible = next((e for e in element if e.tag.endswith('path') and e.attrib.get('stroke') != 'transparent'), None)
    if visible is None:
        continue
    route = segments(visible.attrib['d'])
    edges.append({'id': edge_id, 'binding': facts[edge_id], 'dasharray': visible.attrib.get('stroke-dasharray'), 'segments': route})

relations = []
for e1, e2 in itertools.combinations(edges, 2):
    overlaps = []
    crossings = []
    for i, a in enumerate(e1['segments']):
        for j, b in enumerate(e2['segments']):
            if a['axis'] == b['axis']:
                axis = 0 if a['axis'] == 'H' else 1
                fixed = 1 - axis
                if a['a'][fixed] != b['a'][fixed]:
                    continue
                lo = max(min(a['a'][axis], a['b'][axis]), min(b['a'][axis], b['b'][axis]))
                hi = min(max(a['a'][axis], a['b'][axis]), max(b['a'][axis], b['b'][axis]))
                if hi > lo:
                    overlaps.append({'segment1': i, 'segment2': j, 'axis': a['axis'], 'fixed': a['a'][fixed], 'from': lo, 'to': hi, 'length': hi - lo})
            else:
                h, v = (a, b) if a['axis'] == 'H' else (b, a)
                x, y = v['a'][0], h['a'][1]
                # Strict interior crossing; endpoint contacts are deliberately excluded.
                if min(h['a'][0], h['b'][0]) < x < max(h['a'][0], h['b'][0]) and min(v['a'][1], v['b'][1]) < y < max(v['a'][1], v['b'][1]):
                    crossings.append({'point': [x, y], 'segment1': i, 'segment2': j})
    if overlaps or crossings:
        relations.append({'edge1':e1['id'], 'role1':e1['binding']['role'], 'edge2':e2['id'], 'role2':e2['binding']['role'], 'sameTensor':e1['binding']['tensorId']==e2['binding']['tensorId'], 'collinearOverlaps':overlaps, 'strictInteriorCrossings':crossings})

report = {'kind':'independent-actual-export-route-observation', 'case':case, 'scope':'axis-aligned artifact polyline relations; no legality, necessity, arrow aesthetics or model correctness certification', 'input':{'path':str(source.relative_to(formal)),'bytes':len(raw),'sha256':hashlib.sha256(raw).hexdigest()}, 'edges':edges,'relations':relations,'sameInputAfter':source.read_bytes()==raw}
if output.exists():
    raise RuntimeError('Do not overwrite prior observation')
output.write_text(json.dumps(report, indent=2, ensure_ascii=False)+'\n')
print(json.dumps({'case':case,'relations':relations},ensure_ascii=False))
