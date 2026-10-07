"""Read back current saved bytes without calling the product."""
from pathlib import Path
import hashlib
import json
import sys

ROOT=Path(__file__).resolve().parents[4]
WORK=ROOT/'docs/evidence/m4-draft-port-legibility-work'
OUT=Path(__file__).parent/'saved-residual-readback'
OUT.mkdir(exist_ok=False)
inputs=[];checks=[]
def capture(path):
    data=path.read_bytes();target=OUT/'inputs'/path.relative_to(ROOT) if path.is_relative_to(ROOT) else OUT/'inputs/external'/path.name
    target.parent.mkdir(parents=True,exist_ok=True);target.write_bytes(data)
    inputs.append({'path':str(path),'snapshot':str(target.relative_to(OUT)),'sha256':hashlib.sha256(data).hexdigest(),'bytes':len(data)})
    return data
def check(name,value,detail=None):checks.append({'name':name,'pass':bool(value),'detail':detail})
metadata=json.loads(capture(WORK/'saved-artifacts/residual/manifest.json'))
entry=metadata['files'][0]
saved_bytes=capture(ROOT/entry['snapshot']);saved=json.loads(saved_bytes)
disk_bytes=capture(Path(entry['source']))
baseline=json.loads(capture(ROOT/'docs/evidence/m4-native-matching-work/authoring-artifacts/drafts/draft-e3158996-40d4-4a98-a8f3-c93fc6b79a56.json'))
public=json.loads(capture(WORK/'browser-current-attempt-2/16-residual-saved-reopened.public.json'))['after']
check('new save snapshot exact bytes match actual service draft file',saved_bytes==disk_bytes)
check('new save manifest SHA256 and length',hashlib.sha256(saved_bytes).hexdigest()==entry['sha256'] and len(saved_bytes)==entry['bytes'])
check('current envelope has only draft and storage revision',set(saved)=={'draft','revision'})
old=baseline['draft'];current=saved['draft']
check('new saved draft preserves every old field except monotonic draft revision',{key:value for key,value in current.items() if key!='revision'}=={key:value for key,value in old.items() if key!='revision'})
check('draft revision grows17to31',old['revision']==17 and current['revision']==31)
check('storage revision grows1to2',baseline['revision']==1 and saved['revision']==2,{'before':baseline['revision'],'after':saved['revision']})
check('saved six node identities/order match reopened DOM',[node['id'] for node in current['nodes']]==[node['id'] for node in public['nodes']])
check('saved six binding identities/order match reopened DOM',[edge['id'] for edge in current['edges']]==[edge['id'] for edge in public['edges']])
for index,(node,visible) in enumerate(zip(current['nodes'],public['nodes'])):
    check('saved node '+str(index)+' kind and alias match reopened DOM',node['kind']==visible['kind'] and node['label']==visible['title'])
    check('saved node '+str(index)+' positions match reopened DOM',visible['transform']==f"translate({node['position']['x']} {node['position']['y']})")
    check('saved node '+str(index)+' parameter facts unchanged',node['parameters']==old['nodes'][index]['parameters'])
for index,(edge,old_edge) in enumerate(zip(current['edges'],old['edges'])):
    check('saved binding '+str(index)+' complete typed identity unchanged',edge==old_edge)
capture(Path(__file__))
report={'schema':'archcanvas-current-residual-save-independent/1','pass':all(row['pass'] for row in checks),'checks':checks,'counts':{'checks':len(checks),'pass':sum(row['pass'] for row in checks),'fail':sum(not row['pass'] for row in checks)},'draftRevisions':{'baseline':old['revision'],'current':current['revision']},'storageRevisions':{'baseline':baseline['revision'],'current':saved['revision']},'scope':{'modelExecuted':False,'productImported':False,'pixelInspection':False,'transientMoveParameterComparison':False,'currentSavedFieldsExact':True,'humanTrial':False}}
(OUT/'report.json').write_text(json.dumps(report,ensure_ascii=False,indent=2)+'\n')
readback=[{'path':row['path'],'sourceUnchanged':hashlib.sha256(Path(row['path']).read_bytes()).hexdigest()==row['sha256'],'snapshotMatches':hashlib.sha256((OUT/row['snapshot']).read_bytes()).hexdigest()==row['sha256']} for row in inputs]
(OUT/'manifest.json').write_text(json.dumps({'inputs':inputs,'readback':readback,'pass':all(row['sourceUnchanged'] and row['snapshotMatches'] for row in readback)},indent=2)+'\n')
print(json.dumps({'pass':report['pass'],'counts':report['counts'],'inputs':len(inputs),'failed':[row for row in checks if not row['pass']]},ensure_ascii=False))
sys.exit(0 if report['pass'] else 2)
