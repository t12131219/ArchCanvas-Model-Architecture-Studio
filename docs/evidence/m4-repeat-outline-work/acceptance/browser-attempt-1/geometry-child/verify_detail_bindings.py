"""Bind each of the five hidden detail projections to saved architecture and XML."""
import hashlib
import json
import xml.etree.ElementTree as ET
from pathlib import Path

OUT=Path(__file__).resolve().parent
PROJECT=OUT.parents[5]
RAW=PROJECT/'docs/evidence/m4-repeat-outline-work/browser/attempt-1/transformer-encoder-detail'
FILES=[RAW/'saved-envelope.json',RAW/'figure.svg',RAW/'preview.svg',OUT/'report-final.json']
REPLAY=OUT.parent/'replay/transformer-encoder-detail.export-scene.json'
FILES.append(REPLAY)


def bind(p):
    data=p.read_bytes()
    return {'path':str(p.relative_to(PROJECT)),'bytes':len(data),'sha256':hashlib.sha256(data).hexdigest()}


def main():
    before=[bind(p) for p in FILES]
    saved=json.loads(FILES[0].read_text())['document']
    arch=saved['architecture']
    canonical_edges={e['id']:e for e in arch['edges']}
    canonical_nodes={n['id']:n for n in arch['nodes']}
    geometry=json.loads((OUT/'report-final.json').read_text())
    # Replay is observed output only. The expected canonical edge, target parent,
    # representative typed input and literal circle came from saved architecture/XML.
    replay=json.loads(REPLAY.read_text())
    replay_ports={p['id']:(n['id'],p) for n in replay['nodes'] for p in n['ports']}
    records=[]
    for path in FILES[1:3]:
        xml=ET.fromstring(path.read_text())
        metadata=json.loads(xml.find('{http://www.w3.org/2000/svg}metadata').text)
        scene_bindings={e['sceneEdgeId']:e for e in metadata['renderedBindings']}
        scope_bindings={e['edgeId']:e for e in metadata['exportScope']['boundaryEdges']}
        public_circles={e.get('data-port-id'):e for e in xml.iter('{http://www.w3.org/2000/svg}circle') if e.get('data-port-id')}
        rendered_nodes={e.get('data-node-id'):e for e in xml.iter('{http://www.w3.org/2000/svg}g') if e.get('data-canonical-id')}
        projections=[r for r in geometry['hierarchyProjections'] if r['input']==str(path.relative_to(PROJECT))]
        if len(projections)!=5:raise AssertionError('Expected exactly five projections per SVG')
        for p in projections:
            eid=p['edgeId']; original=canonical_edges[eid]; scene=scene_bindings[eid]; scope=scope_bindings[eid]
            check_fields=['source','target','tensorId','role']
            original_vs_scene=all(original[k]==scene[k] for k in check_fields)
            original_vs_scope=all(original[k]==scope[k] for k in check_fields)
            target=original['target']; target_node=canonical_nodes[target['nodeId']]
            canonical_port=next(q for q in target_node['ports'] if q['id']==target['portId'])
            owner=canonical_nodes[p['ownerSceneNodeId']]
            representative=next(q for q in owner['ports'] if q['id']==p['representativeCanonicalPortId'])
            circle=public_circles[p['portId']]
            actual_point=[float(circle.get('cx')),float(circle.get('cy'))]
            replay_owner,replay_port=replay_ports[p['portId']]
            expected_representative={'nodeId':owner['id'],'portId':representative['id']}
            checks={'savedEdgeMatchesRenderedBinding':original_vs_scene,
                    'savedEdgeMatchesExportScopeBinding':original_vs_scope,
                    'hiddenCanonicalTargetMetadataPreserved':scene['target']==p['canonicalEndpoint'],
                    'savedParentMatchesVisibleOwner':target_node['parentId']==owner['id'],
                    'hiddenPortRoleDirectionMatchesRepresentative':canonical_port['role']==representative['role']==original['role'] and canonical_port['direction']==representative['direction']=='in',
                    'visibleOwnerIsLiteralPublicNode':owner['id'] in rendered_nodes,
                    'circleOwnerMatchesVisibleOwner':circle.get('data-node-id')==owner['id'],
                    'circleMatchesRecordedEndpointExact':actual_point==p['publicPortPoint'] and actual_point==p['routePoint'],
                    'sourceAndIRDigestsMatch':metadata['sourceDigest']==arch['sourceDigest'] and metadata['irDigest']==arch['irDigest'],
                    'canvasIdentityAndRevisionMatch':metadata['documentId']==saved['id'] and metadata['revision']==saved['revision'],
                    'observedScenePortCanonicalBindingsContainHiddenTarget':target in replay_port['canonicalBindings'],
                    'observedScenePortCanonicalBindingsContainRepresentative':expected_representative in replay_port['canonicalBindings'],
                    'observedScenePortCanonicalEdgeIdsContainEdge':eid in replay_port['canonicalEdgeIds'],
                    'observedScenePortOwnerRoleDirectionMatchLiteralExpected':replay_owner==owner['id'] and replay_port['role']==original['role'] and replay_port['direction']=='in',
                    'observedScenePortPointMatchesLiteralCircle':max(abs(replay_port[k]-actual_point[i]) for i,k in enumerate(['x','y']))<=.051}
            if not all(checks.values()):raise AssertionError({'input':str(path),'edgeId':eid,'checks':checks})
            records.append({'input':str(path.relative_to(PROJECT)),'edgeId':eid,'role':original['role'],
                            'hiddenCanonicalTarget':target,'hiddenCanonicalTypedPort':canonical_port,
                            'visibleCanonicalOwner':owner['id'],'savedParentId':target_node['parentId'],
                            'visibleCanonicalRepresentativePort':representative,
                            'actualPublicCircleId':p['portId'],'actualPublicCircleOwner':circle.get('data-node-id'),
                            'actualPublicCirclePoint':actual_point,'routeEndpointPoint':p['routePoint'],
                            'observedScenePortCanonicalBindings':replay_port['canonicalBindings'],
                            'observedScenePortCanonicalEdgeIds':replay_port['canonicalEdgeIds'],
                            'checks':checks})
    after=[bind(p) for p in FILES]
    if before!=after:raise AssertionError('Inputs changed')
    # Membership controls distinguish this specific binding from a generic
    # "some visible ancestor" exemption.
    sample=records[0]
    actual=replay_ports[sample['actualPublicCircleId']][1]
    valid_membership=lambda port,record: record['hiddenCanonicalTarget'] in port['canonicalBindings'] and record['edgeId'] in port['canonicalEdgeIds']
    removed_hidden={**actual,'canonicalBindings':[x for x in actual['canonicalBindings'] if x!=sample['hiddenCanonicalTarget']]}
    removed_edge={**actual,'canonicalEdgeIds':[x for x in actual['canonicalEdgeIds'] if x!=sample['edgeId']]}
    controls={'actual_specific_membership_accepted':valid_membership(actual,sample),
              'removed_hidden_binding_rejected':not valid_membership(removed_hidden,sample),
              'removed_canonical_edge_id_rejected':not valid_membership(removed_edge,sample)}
    if not all(controls.values()):raise AssertionError(controls)
    report={'schema':'independent-detail-hidden-port-projection-binding/1.0','inputHashesBefore':before,'inputHashesAfter':after,
            'inputHashesUnchanged':True,'records':records,'checksPassed':sum(len(r['checks']) for r in records),
            'negativeControls':controls,'replayRole':'Observed actual ScenePort output is checked against independently derived saved hierarchy, typed port role/direction, literal public circle, and metadata canonical edge. Replay is not the expected oracle.',
            'scope':'Five hidden target projections repeated in detail preview and export; role/direction and captured saved hierarchy independently bind each canonical target to its actual public SVG circle, then actual ScenePort canonicalBindings and canonicalEdgeIds must cover that exact hidden target and edge. No product code imports; no changes to source facts.'}
    with (OUT/'detail-projection-bindings.json').open('x') as f:json.dump(report,f,ensure_ascii=False,indent=2);f.write('\n')
    lines=['# Exact detail projection bindings','',
           'All ten records (five in each detail preview/export) retain their canonical edge/source/target/tensor/role metadata and match the saved architecture. The visible circles belong to the captured hidden targets’ direct collapsed parent; typed input role/direction matches.',
           '', '| Canonical edge | Hidden target port | Visible parent input | Actual public circle / route endpoint |',
           '| --- | --- | --- | --- |']
    for r in records[:5]:
        lines.append(f"| {r['edgeId']} | {r['hiddenCanonicalTypedPort']['name']} ({r['role']}) | {r['visibleCanonicalOwner'].split('.')[-1]}:{r['visibleCanonicalRepresentativePort']['name']} | {r['actualPublicCirclePoint']} |")
    lines+=['', 'Per-record exact public circle IDs, captured saved parent IDs, hidden and representative typed canonical ports, metadata checks, and five unchanged input bindings are in detail-projection-bindings.json. Actual replay ScenePort canonicalBindings and canonicalEdgeIds contain each specific hidden canonical target and edge; replay is observed output, not the expected oracle. Removing the hidden binding or canonical edge ID is rejected by negative controls. These facts establish the nominal projection binding only; the blocked up-move route remains a separate observed failure state.']
    with (OUT/'detail-projection-bindings.md').open('x') as f:f.write('\n'.join(lines)+'\n')
    print(json.dumps({'receipt':bind(OUT/'detail-projection-bindings.json'),'summary':bind(OUT/'detail-projection-bindings.md'),'checks':report['checksPassed'],'records':len(records)},indent=2))


if __name__=='__main__':main()
