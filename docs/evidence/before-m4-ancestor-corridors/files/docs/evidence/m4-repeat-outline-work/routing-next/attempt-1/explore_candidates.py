"""Read-only independent serialized geometry experiment; no product edits."""
from pathlib import Path
from itertools import combinations
from hashlib import sha256
import json, re, copy

WORK = Path(__file__).resolve().parent
EPS = .01
scene = json.loads((WORK / 'current/transformer-level3-paper-180.scene.json').read_bytes())

def points(path):
    result = []; x = y = 0.0
    for op, first, second in re.findall(r'([MLHV])\s*(-?[\d.]+)(?:\s+(-?[\d.]+))?', path):
        if op in ('M', 'L'): x, y = float(first), float(second)
        elif op == 'H': x = float(first)
        else: y = float(first)
        if not result or (x, y) != result[-1]: result.append((x, y))
    return result

def merged_length(intervals):
    total = 0; last = None
    for a, b in sorted(intervals):
        if last is None: last = [a, b]
        elif a <= last[1] + EPS: last[1] = max(last[1], b)
        else: total += last[1] - last[0]; last = [a, b]
    return total + (last[1] - last[0] if last else 0)

def pair(a, b):
    crossings = set(); overlaps = {}
    for p, q in zip(a, a[1:]):
        for r, s in zip(b, b[1:]):
            av, bv = p[0] == q[0], r[0] == s[0]
            if av != bv:
                v, w, h, j = (p, q, r, s) if av else (r, s, p, q)
                if min(h[0], j[0]) + EPS < v[0] < max(h[0], j[0]) - EPS and min(v[1], w[1]) + EPS < h[1] < max(v[1], w[1]) - EPS:
                    crossings.add((v[0], h[1]))
            elif abs(p[0 if av else 1] - r[0 if av else 1]) < EPS:
                axis = 1 if av else 0
                low = max(min(p[axis], q[axis]), min(r[axis], s[axis])); high = min(max(p[axis], q[axis]), max(r[axis], s[axis]))
                if high - low > EPS: overlaps.setdefault(('v' if av else 'h', p[1-axis]), []).append((low, high))
    length = sum(merged_length(intervals) for intervals in overlaps.values())
    return {'crossingPairs': int(bool(crossings)), 'crossingPoints': len(crossings), 'overlapPairs': int(bool(length)), 'overlapLength': round(length, 5)}

def metrics(edges):
    totals = {key: 0 for key in ['crossingPairs', 'crossingPoints', 'overlapPairs', 'overlapLength', 'disjointCrossingPairs', 'disjointCrossingPoints', 'disjointOverlapPairs']}
    records = {}
    for a, b in combinations(edges, 2):
        if a['tensorId'] == b['tensorId']: continue
        metric = pair(points(a['path']), points(b['path']))
        if metric['crossingPairs'] or metric['overlapPairs']: records[(a['id'], b['id'])] = metric
        for key, value in metric.items(): totals[key] += value
        if not {a['sourceId'], a['targetId']} & {b['sourceId'], b['targetId']}:
            for key in ['crossingPairs', 'crossingPoints', 'overlapPairs']: totals['disjoint' + key[0].upper() + key[1:]] += metric[key]
    totals['overlapLength'] = round(totals['overlapLength'], 5)
    return totals, records

nodes = {n['id']: n for n in scene['nodes']}
def ancestors(id):
    result = set(); parent = nodes[id].get('parentId')
    while parent: result.add(parent); parent = nodes.get(parent, {}).get('parentId')
    return result

def bodies(node):
    offsets = [0, 3.5, 7] if node.get('repeat') and not node['expanded'] else [0]
    return [(node['x']+d, node['y']+d, node['x']+node['width']+d, node['y']+node['height']+d) for d in offsets]

def intrusions(edge):
    excluded = ancestors(edge['sourceId']) | ancestors(edge['targetId']); rectangles = []
    for id, node in nodes.items():
        if id in excluded:
            if node['expanded']: rectangles.append((id, (node['x'], node['y'], node['x']+node['width'], node['y']+node['headerHeight'])))
        else: rectangles.extend((id, rectangle) for rectangle in bodies(node))
    result = set(); path = points(edge['path'])
    for a, b in zip(path, path[1:]):
        for id, (left, top, right, bottom) in rectangles:
            if a[0] == b[0]: hit = left+EPS < a[0] < right-EPS and max(min(a[1], b[1]), top+EPS) < min(max(a[1], b[1]), bottom-EPS)
            elif a[1] == b[1]: hit = top+EPS < a[1] < bottom-EPS and max(min(a[0], b[0]), left+EPS) < min(max(a[0], b[0]), right-EPS)
            else: raise ValueError('nonorthogonal')
            if hit: result.add(id)
    return sorted(result)

before, before_pairs = metrics(scene['edges'])
proposals = [
    ('source-mask-first-frame', {'edge:7': 'M 479 196 V 204 H 58 V 458 H 319.33 V 472'}),
    ('source-mask-first-attention', {'edge:11': 'M 479 196 V 204 H 58 V 520 H 269.33 V 534'}),
    ('source-mask-second-attention-arrival', {'edge:29': 'M 479 196 V 202 H 66 V 1704 H 269.33 V 1718'}),
    ('memory-overview-left-corridor', {'edge:44': 'M 237 2772 V 2785 H 462 V 397 H 621.6 V 410'}),
    ('decoder-residual-left-corridor', {'edge:58': 'M 655.3 734 V 747 H 520 V 859 H 590.7 V 872'}),
    ('source-mask-first-frame-two-corridors', {'edge:7': 'M 479 196 V 204 H 560 V 378 H 490 V 460 H 319.33 V 472'}),
    ('memory-residual-two-local-swaps', {'edge:44': 'M 237 2772 V 2785 H 462 V 397 H 621.6 V 410', 'edge:58': 'M 655.3 734 V 747 H 520 V 859 H 590.7 V 872'}),
    ('memory-family-left-common-trunk', {'edge:44': 'M 237 2772 V 2778 H 467 V 397 H 621.6 V 410', 'edge:55': 'M 237 2772 V 2778 H 467 V 766 H 623 V 772'}),
]
reports=[]
for name, replacements in proposals:
    candidate = copy.deepcopy(scene['edges'])
    for edge in candidate:
        if edge['id'] in replacements: edge['path'] = replacements[edge['id']]
    after, after_pairs = metrics(candidate)
    changed=[]
    for key in before_pairs.keys() | after_pairs.keys():
        old=before_pairs.get(key, pair([], [])); new=after_pairs.get(key, pair([], []))
        if old != new: changed.append({'pair':key,'before':old,'after':new})
    selected=[edge for edge in candidate if edge['id'] in replacements]
    report={'candidateId':name,'paths':replacements,'before':before,'after':after,'changes':changed,
      'blockedBodiesOrAncestorHeaders':{edge['id']:intrusions(edge) for edge in selected},
      'allEndpointsUnchanged':all(points(edge['path'])[0] == points(next(e for e in scene['edges'] if e['id']==edge['id'])['path'])[0] and points(edge['path'])[-1] == points(next(e for e in scene['edges'] if e['id']==edge['id'])['path'])[-1] for edge in selected),
      'routerProtectedCountsNoWorse':all(after[key] <= before[key] for key in before if key != 'overlapLength'),
      'noNewDifferentTensorPair':not(after_pairs.keys()-before_pairs.keys()),
      'routeLengthBeforeAfter':{edge['id']:[sum(abs(a[0]-b[0])+abs(a[1]-b[1]) for a,b in zip(points(next(e for e in scene['edges'] if e['id']==edge['id'])['path']), points(next(e for e in scene['edges'] if e['id']==edge['id'])['path'])[1:])),sum(abs(a[0]-b[0])+abs(a[1]-b[1]) for a,b in zip(points(edge['path']),points(edge['path'])[1:]))] for edge in selected}}
    report['sameTensorPairChanges']=[]
    for a,b in combinations(scene['edges'],2):
        if a['tensorId'] != b['tensorId'] or not ({a['id'],b['id']} & replacements.keys()): continue
        old=pair(points(a['path']),points(b['path'])); new=pair(points(replacements.get(a['id'],a['path'])),points(replacements.get(b['id'],b['path'])))
        if old!=new: report['sameTensorPairChanges'].append({'pair':[a['id'],b['id']],'sameCanonicalSource':a['source']==b['source'],'sameRoleAndStyle':all(a[k]==b[k] for k in ['role','stroke','width','dashed']),'before':old,'after':new})
    reports.append(report)

# Independent cross-reduction search changes only the main lane and two local
# gates of existing six-point routes; frozen endpoints and source normals stay.
search=[]
for edge in scene['edges']:
    p=points(edge['path'])
    if len(p)!=6 or not(p[0][0]==p[1][0] and p[1][1]==p[2][1] and p[2][0]==p[3][0] and p[3][1]==p[4][1] and p[4][0]==p[5][0]):continue
    if p[0][1]>=p[1][1] or p[-1][1]<=p[-2][1]:continue
    old=before
    for lane in sorted({p[2][0]+d for d in [-24,-16,-8,8,16,24]}):
      for gate0 in [p[1][1]-8,p[1][1],p[1][1]+8]:
       for gate1 in [p[3][1]-8,p[3][1],p[3][1]+8]:
        if gate0<=p[0][1] or gate1>=p[-1][1]:continue
        path=f'M {p[0][0]:g} {p[0][1]:g} V {gate0:g} H {lane:g} V {gate1:g} H {p[-1][0]:g} V {p[-1][1]:g}'
        replacement={**edge,'path':path}
        if intrusions(replacement):continue
        candidate=[replacement if e['id']==edge['id'] else e for e in scene['edges']]
        after, pairs=metrics(candidate)
        if after['crossingPairs']<old['crossingPairs'] and all(after[key]<=old[key] for key in old if key!='overlapLength'):
            search.append({'edgeId':edge['id'],'path':path,'before':old,'after':after})
search.sort(key=lambda r:(r['after']['crossingPairs'],r['after']['overlapLength']))
report={'scope':'Hypothetical read-only geometry; no production reroute/binding/browser acceptance', 'representativeCase':'transformer-level3-paper-180','currentCounts':before,'proposals':reports,'crossReductionSearchCount':len(search),'crossReductionSearchFirst10':search[:10]}
out=WORK/'candidate-experiments-v3.json';out.write_text(json.dumps(report,ensure_ascii=False,indent=2)+'\n')
print(json.dumps({'report':str(out),'sha256':sha256(out.read_bytes()).hexdigest(),'counts':before,'candidates':[{k:r[k] for k in ['candidateId','after','blockedBodiesOrAncestorHeaders','allEndpointsUnchanged','routerProtectedCountsNoWorse','noNewDifferentTensorPair']} for r in reports],'crossReductionSearchCount':len(search),'crossFirst':search[:2]}))
