"""Distinguish the public body rectangle from its Repeat visual backplates."""
import hashlib
import json
import xml.etree.ElementTree as ET
from pathlib import Path
HERE = Path(__file__).resolve().parent
ROOT = HERE.parents[3]
SOURCE = ROOT / 'docs/evidence/m4-monochrome-role-work/browser-current/cnn-level0-paper-180/figure.svg'
RAW = ROOT / 'docs/evidence/m4-monochrome-role-work/browser-current/cnn-level0-paper-180/document.json'

def bind(path):
    b=path.read_bytes()
    return {'path':str(path.relative_to(ROOT)),'bytes':len(b),'sha256':hashlib.sha256(b).hexdigest()}

paths=[Path(__file__).resolve(),SOURCE,RAW,HERE/'diagnosis.json']
before=[bind(p) for p in paths]
xml=ET.fromstring(SOURCE.read_bytes())
repeat_id='repeat:instance:model.ResidualCNN.blocks'
pool_id='call:instance:model.ResidualCNN.pool'
groups={g.get('data-node-id'):g for g in xml.iter() if g.get('data-canonical-id') and g.get('data-node-id')}
rects=[{name:float(r.get(name)) for name in ['x','y','width','height']} for r in groups[repeat_id] if r.tag.split('}')[-1]=='rect']
pool_body=next(r for r in groups[pool_id] if r.tag.split('}')[-1]=='rect' and r.get('stroke-width') is not None)
pool_top=float(pool_body.get('y'))
outline_bottom=max(r['y']+r['height'] for r in rects)
document=json.loads(RAW.read_text());root_key='call:instance:model.ResidualCNN'
delta=document['layoutByFrontier'][root_key][pool_id]['y']-document['layout'][pool_id]['y']
after=[bind(p) for p in paths]
result={'protocol':'archcanvas-collapse-continuity-public-outline-supplement/1',
        'explanation':'Initial diagnosis deliberately used the stroked front body (bottom416/gap1614). Actual Repeat visible outline includes the backplate ending423; its visible clearance gap is1607. This is a definition distinction, not mutated evidence.',
        'repeatPublicDirectRectangles':rects,'repeatVisibleOutlineBottom':outline_bottom,'poolPublicBodyTop':pool_top,
        'visibleOutlineGap':pool_top-outline_bottom,'existingSnapshotPoolLocalDeltaY':delta,
        'expectedPoolBodyTopUsingPriorRootLocalSnapshot':pool_top+delta,
        'expectedVisibleClearanceGapUsingPriorRootLocalSnapshot':pool_top+delta-outline_bottom,
        'expectationScope':'Prior saved local-position arithmetic, not execution of a repaired renderer or claim of actual browser recovery.',
        'inputBindingsBefore':before,'inputBindingsAfter':after,'inputsUnchanged':before==after,
        'productEdited':False,'productExecuted':False,'browserOperated':False,'humanParticipants':0}
with (HERE/'outline-supplement.json').open('x') as f:json.dump(result,f,ensure_ascii=False,indent=2);f.write('\n')
print(json.dumps({'receipt':bind(HERE/'outline-supplement.json'),'inputsUnchanged':before==after,'visibleGap':result['visibleOutlineGap'],'priorSnapshotExpectedGap':result['expectedVisibleClearanceGapUsingPriorRootLocalSnapshot']}))
assert before==after
