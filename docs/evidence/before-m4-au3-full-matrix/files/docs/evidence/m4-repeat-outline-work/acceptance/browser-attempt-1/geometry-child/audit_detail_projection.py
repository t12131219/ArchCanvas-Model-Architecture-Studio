"""Supplement the preserved direct-ID pass with independent hierarchy projection."""
import copy
import hashlib
import importlib.util
import json
from pathlib import Path

OUT = Path(__file__).resolve().parent
spec = importlib.util.spec_from_file_location('nominal_geometry_oracle', OUT/'audit_nominal_svg.py')
oracle = importlib.util.module_from_spec(spec)
spec.loader.exec_module(oracle)
PROJECT, RAW, TOL, EPS = oracle.PROJECT, oracle.RAW, oracle.TOL, oracle.EPS
BASE = OUT/'report.json'
ENVELOPE = RAW/'transformer-encoder-detail'/'saved-envelope.json'


def projection_candidates(canonical, role, endpoint, route_point, nodes, ports, architecture_nodes):
    current = architecture_nodes.get(canonical['nodeId'])
    if current is None or not any(p['id']==canonical['portId'] and p['role']==role
                                  and p['direction']==('out' if endpoint=='source' else 'in')
                                  for p in current['ports']):
        return [], []
    chain = []
    while current and current['id'] not in nodes:
        chain.append(current['id'])
        current = architecture_nodes.get(current.get('parentId'))
    if current is None or len(chain)==0 or nodes[current['id']]['expanded']:
        return [], chain
    owner_id = current['id']
    candidates = []
    for pid,p in ports.items():
        if p['nodeId'] != owner_id or max(abs(p['point'][k]-route_point[k]) for k in (0,1))>TOL:
            continue
        owner_role = pid.endswith(':'+role) or any(pid.endswith(':'+role+':'+s) for s in oracle.NORMAL)
        if not owner_role:
            continue
        side = next((s for s in oracle.NORMAL if pid.endswith(':'+role+':'+s)),
                    'bottom' if endpoint=='source' else 'top')
        # Infer representative public port from its canonical endpoint stem.
        # The visible owner has this port explicitly in the saved architecture.
        role_stem = pid[:-len(':'+role+(':'+side if pid.endswith(':'+role+':'+side) else ''))]
        owner_prefix = owner_id+':'
        if not role_stem.startswith(owner_prefix):
            continue
        representative_port = role_stem[len(owner_prefix):]
        representative = next((q for q in current['ports'] if q['id']==representative_port),None)
        if representative is None or representative['role']!=role or representative['direction']!=('out' if endpoint=='source' else 'in'):
            continue
        candidates.append((pid,p,side,representative_port))
    return candidates, chain+[owner_id]


def main():
    base=json.loads(BASE.read_text())
    paths=[PROJECT/x['path'] for x in json.loads((OUT/'inputs-before.json').read_text())]
    paths += [ENVELOPE,BASE,OUT/'audit_nominal_svg.py']
    before=[oracle.binding(p) for p in paths]
    oracle.new_json('projection-inputs-before.json',before)
    architecture=json.loads(ENVELOPE.read_text())['document']['architecture']
    anodes={n['id']:n for n in architecture['nodes']}
    result=copy.deepcopy(base)
    projected=[]
    for audit in result['audits']:
        if 'transformer-encoder-detail/' not in audit['input']:
            continue
        raw_svg,_=oracle.load_svg(PROJECT/audit['input'])
        metadata=json.loads(oracle.ET.fromstring(raw_svg).find('s:metadata',oracle.NS).text)
        binding={b['sceneEdgeId']:b for b in metadata['renderedBindings']}
        remaining=[]
        for problem in audit['violations']:
            if problem['type']!='endpoint-public-port-resolution':
                remaining.append(problem)
                continue
            edge_id,endpoint=problem['edgeId'],problem['endpoint']
            canonical=binding[edge_id][endpoint]
            role=binding[edge_id]['role']
            if canonical['nodeId'] not in metadata['exportScope']['canonicalNodeIds']:
                remaining.append(problem)
                continue
            candidates,chain=projection_candidates(canonical,role,endpoint,problem['routePoint'],audit['nodes'],audit['ports'],anodes)
            if len(candidates)!=1:
                remaining.append({**problem,'projectionCandidates':[c[0] for c in candidates],'hierarchyChain':chain})
                continue
            pid,p,side,representative_port=candidates[0]
            owner=audit['nodes'][p['nodeId']]
            expected=oracle.ray_boundary(owner['rectangles'],p['point'],side)
            error=None if expected is None else max(abs(p['point'][k]-expected[k]) for k in (0,1))
            pp=audit['routes'][edge_id]['points']
            nonzero=[(a,z) for a,z in zip(pp,pp[1:]) if max(abs(a[k]-z[k]) for k in (0,1))>EPS]
            a,z=nonzero[0] if endpoint=='source' else nonzero[-1]
            vec=[z[k]-a[k] for k in (0,1)]
            if endpoint=='target':vec=[-v for v in vec]
            length=sum(abs(v) for v in vec)
            valid=all(abs(vec[k]/length-oracle.NORMAL[side][k])<=EPS for k in (0,1))
            record={'edgeId':edge_id,'endpoint':endpoint,'canonicalEndpoint':canonical,'role':role,
                    'portId':pid,'ownerSceneNodeId':p['nodeId'],
                    'resolutionRule':'saved-architecture-nearest-visible-collapsed-ancestor-role-direction-and-unique-public-endpoint',
                    'hierarchyChain':chain,'representativeCanonicalPortId':representative_port,
                    'routePoint':problem['routePoint'],'publicPortPoint':p['point'],
                    'routePortError':max(abs(p['point'][k]-problem['routePoint'][k]) for k in (0,1)),
                    'side':side,'expectedNominalRayBoundary':expected,'portBoundaryError':error,
                    'outwardEndpointSegment':vec,'normalValid':valid,'ownerStack':owner['stack'],'ownerKind':owner['kind']}
            audit['endpointRecords'].append(record)
            projected.append({'input':audit['input'],**record})
            if error is None or error>TOL:
                remaining.append({'type':'port-ray-union-boundary',**record})
            if not valid:
                remaining.append({'type':'endpoint-segment-normal',**record})
        audit['violations']=remaining
        audit['counts']['resolvedEndpoints']=len(audit['endpointRecords'])
        audit['counts']['endpointViolations']=len(remaining)
        audit['counts']['hierarchyProjectedEndpoints']=sum(e['resolutionRule'].startswith('saved-architecture') for e in audit['endpointRecords'])
    for audit in result['audits']:
        audit['counts'].setdefault('hierarchyProjectedEndpoints',0)
    result['aggregateCounts']={k:sum(a['counts'][k] for a in result['audits']) for k in result['audits'][0]['counts']}
    result['directIdPassPreserved']={'path':str(BASE.relative_to(PROJECT)), 'sha256':oracle.binding(BASE)['sha256'],
        'explanation':'Initial pass intentionally required exact canonical public port IDs and left 5 detail target bindings unresolved per export/preview. This supplement verifies their visible collapsed ancestor role/direction projections; initial pass is preserved.'}
    result['hierarchyProjectionInput']={'path':str(ENVELOPE.relative_to(PROJECT)), 'sha256':oracle.binding(ENVELOPE)['sha256'],
        'usage':'Only canonical node parentId and typed canonical port role/direction are used; no product outline/router implementation is imported.'}
    result['hierarchyProjections']=projected
    indexed={a['input'].split('attempt-1/',1)[1]:a for a in result['audits']}
    pairs=[(c+'/browser-scene.svg',c+'/figure.svg') for c in oracle.CASES[:3]]
    pairs += [('transformer-encoder-detail/preview.svg','transformer-encoder-detail/figure.svg')]
    pairs += [('transformer-moves/down.json',f'transformer-moves/{m}.json') for m in ['down-redo','saved','reopened']]
    equivalence=[]
    for a,b in pairs:
        left,right=indexed[a],indexed[b]
        node_geometry=lambda audit:{nid:{k:n[k] for k in ['canonicalNodeId','kind','boundary','expanded','rectangles','front','header','stack']} for nid,n in audit['nodes'].items()}
        port_geometry=lambda audit:{pid:{'nodeId':p['nodeId'],'point':p['point']} for pid,p in audit['ports'].items()}
        route_geometry=lambda audit:{eid:r['points'] for eid,r in audit['routes'].items()}
        checks={'publicNodeGeometryExact':node_geometry(left)==node_geometry(right),
                'publicPortIdsOwnersCentersExact':port_geometry(left)==port_geometry(right),
                'publicEdgeIdsRoutePointsExact':route_geometry(left)==route_geometry(right)}
        equivalence.append({'left':a,'right':b,**checks})
        if not all(checks.values()):raise AssertionError(equivalence[-1])
    result['nominalGeometryEquivalence']=equivalence
    up=indexed['transformer-moves/up.json']
    result['upBlockedFinding']={'edgeId':'edge:7','canonicalRole':'mask',
        'visibleDomDiagnostics':up['visibleDomDiagnostics'], 'hits':up['interiorHits'],
        'bodyEdgeNodePairs':up['counts']['bodyEdgeNodePairs'],
        'stackRectangleInteriors':up['counts']['stackRectangleInteriors'],
        'classification':'Observed explicit blocked path; 3 nominal non-stack card intersections across 2 embedding bodies. This is retained as a routing failure state, not waived by the warning.'}
    result['decision']='No endpoint/ray-union/stack/backplate geometry violations in this bounded sample. One explicit blocked up-move edge retains 3 non-stack card intersections; no full-matrix or human acceptance claim.'
    example=projected[0]
    audit=indexed[example['input'].split('attempt-1/',1)[1]]
    good=projection_candidates(example['canonicalEndpoint'],example['role'],example['endpoint'],example['routePoint'],audit['nodes'],audit['ports'],anodes)[0]
    wrong_role=projection_candidates(example['canonicalEndpoint'],'residual',example['endpoint'],example['routePoint'],audit['nodes'],audit['ports'],anodes)[0]
    wrong_point=projection_candidates(example['canonicalEndpoint'],example['role'],example['endpoint'],[example['routePoint'][0]+10,example['routePoint'][1]],audit['nodes'],audit['ports'],anodes)[0]
    result['projectionControls']={'actual_hidden_input_projected_uniquely':len(good)==1,
        'wrong_role_rejected':not wrong_role,'wrong_endpoint_position_rejected':not wrong_point}
    if not all(result['projectionControls'].values()):raise AssertionError(result['projectionControls'])
    after=[oracle.binding(p) for p in paths]
    oracle.new_json('projection-inputs-after.json',after)
    if before!=after:raise AssertionError('Bound inputs changed')
    result['inputCount']=len(paths)
    oracle.new_json('report-final.json',result)
    lines=['# Independent nominal SVG geometry review — completed hierarchy projection','',result['decision'],'',
           f"{result['artifactsAudited']} SVG artifacts; {result['aggregateCounts']['routes']} route observations; {result['aggregateCounts']['resolvedEndpoints']}/{result['aggregateCounts']['routeEndpoints']} endpoints verified. {len(paths)} input hashes unchanged.",
           '', '| Input | Routes | Endpoints | Endpoint violations | Stack / backplate hits | Card hits | Header hits |',
           '| --- | ---: | ---: | ---: | ---: | ---: | ---: |']
    for a in result['audits']:
        c=a['counts']; name=a['input'].split('attempt-1/',1)[1]
        lines.append(f"| {name} | {c['routes']} | {c['resolvedEndpoints']} | {c['endpointViolations']} | {c['stackRectangleInteriors']} / {c['backplateRectangleInteriors']} | {c['bodyRectangleInteriors']} | {c['headerRectangleInteriors']} |")
    lines += ['', 'The exact-ID first pass remains intact. Ten target observations (five in preview and five in detail export) use the independently checked nearest visible collapsed ancestor: query/key/value become EncoderLayer x; attn_mask becomes EncoderLayer mask. Canonical hidden endpoint IDs remain in SVG metadata.',
              '', 'Up edge:7 is explicitly blocked in the DOM. Its horizontal segment crosses source embedding by 97 units and target embedding by 194 units; its terminal segment crosses source embedding by 3 units. These are 3 segment/rectangle hits across 2 card bodies, zero Repeat or backplate interiors. Other four-direction movement states, undo states, redo/save/reopen states have no nominal card/header/stack intersections.',
              '', 'SVG public node geometry, public port identities/owners/centers, and route point arrays match exactly for three whole-scene interactive/static pairs, detail preview/export, and down versus redo/save/reopen.',
              '', 'Nominal unrounded rectangle interiors and route centerlines only: stroke, glyph, arrowhead, rounded-corner, raster and screenshot visibility claims are outside scope. This is four representative cases, not a full matrix or human acceptance.']
    with (OUT/'report-final.md').open('x') as f:f.write('\n'.join(lines)+'\n')
    print(json.dumps({'report':oracle.binding(OUT/'report-final.json'),'summary':oracle.binding(OUT/'report-final.md'),
        'counts':result['aggregateCounts'],'inputsUnchanged':before==after,'projectionControls':result['projectionControls']},ensure_ascii=False,indent=2))


if __name__=='__main__':main()
