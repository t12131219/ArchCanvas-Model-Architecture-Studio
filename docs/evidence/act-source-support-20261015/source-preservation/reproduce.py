from copy import deepcopy
import hashlib
import json
from pathlib import Path
import time

from archcanvas_authoring import generate_model, validate_draft, DraftError
from archcanvas_python import analyze_project

project = Path(__file__).resolve().parents[4]
act = project.parent / 'Constraint relationship of architecture diagram' / 'act'
evidence = project / 'docs/evidence/act-source-support-20261015/source-preservation'
evidence.mkdir(parents=True, exist_ok=True)
def manifest():
 return {path.relative_to(act).as_posix(): {'sha256':hashlib.sha256(path.read_bytes()).hexdigest(),'bytes':path.stat().st_size,'mtimeNs':path.stat().st_mtime_ns} for path in sorted(act.rglob('*')) if path.is_file()}
def write(name,value): (evidence/name).write_text(json.dumps(value,ensure_ascii=False,indent=2)+'\n')
before = manifest()
write('source-before.json', before)
# Build the normal compact editing frontier, never route the complete inspection tree.
from subprocess import run
def compact_draft(architecture):
 script="import fs from 'node:fs';import {createDocument,buildScene} from './src/core/index.ts';let document=createDocument(JSON.parse(fs.readFileSync(0,'utf8')));process.stdout.write(JSON.stringify({document,scene:buildScene(document)}));"
 rendered=run(['node','--experimental-strip-types','--input-type=module','-e',script],cwd=project/'studio',input=json.dumps(architecture),text=True,capture_output=True,check=True)
 view=json.loads(rendered.stdout)
 from archcanvas_authoring import import_source_draft
 return import_source_draft(view['document'],view['scene'])['draft']
t=time.monotonic();original=analyze_project(act,'detr.models.detr_vae:DETRVAE')
draft=compact_draft(original)
write('initial-draft.json',draft)
unchanged=generate_model(draft)
write('unchanged-generation.json',unchanged)
refs=draft['sourceProvenance']['nodeRefs']
target = next(node for node in draft['nodes'] if refs[node['id']]['nodeId']=='call:instance:detr.models.detr_vae.DETRVAE.is_pad_head')
assert target['parameters']['out_features']==1
target['parameters']['out_features']=2
result=generate_model(draft)
write('edited-generation.json',result)
managed=evidence/'managed-copy'
managed.mkdir(exist_ok=True)
for item in result['architecture']['sources']:
 path=managed/item['path'];path.parent.mkdir(parents=True,exist_ok=True);path.write_text(item['content'])
replayed=analyze_project(managed,result['entry'])
assert replayed==result['architecture']
changed=[item['path'] for item in replayed['sources'] if item['digest']!=next(source['digest'] for source in original['sources'] if source['path']==item['path'])]
assert changed==['detr/models/detr_vae.py'], changed
old=next(item['content'] for item in original['sources'] if item['path']==changed[0])
new=next(item['content'] for item in replayed['sources'] if item['path']==changed[0])
assert new==old.replace('self.is_pad_head = nn.Linear(hidden_dim, 1)','self.is_pad_head = nn.Linear(hidden_dim, 2)')
structural=deepcopy(draft)
output=next(node for node in structural['nodes'] if refs[node['id']]['kind']=='Output')
input_node=next(node for node in structural['nodes'] if refs[node['id']]['kind']=='Input' and node['label']=='qpos')
input_spec=next(item for item in structural['sourceProvenance']['modules'] if item['kind']==input_node['kind'])
edge=next(item for item in structural['edges'] if item['target']['nodeId']==output['id'])
edge['source']={'nodeId':input_node['id'],'portId':next(port['id'] for port in input_spec['ports'] if port['direction']=='out')}
assert validate_draft(structural)['complete']
assert not validate_draft(structural)['generation']['supported']
try:generate_model(structural)
except DraftError as error: rejected={'error':str(error),'diagnostics':error.diagnostics}
else:raise AssertionError('Changed relation was accepted')
after=manifest()
assert before==after
old_manifest=json.loads((project.parent / 'Temp/act-readonly-evaluation-20261015/source-before.json').read_text())
assert after==old_manifest
write('source-after.json',after)
write('summary.json',{'status':'passed','entry':result['entry'],'inputNodes':len(original['nodes']),'inputEdges':len(original['edges']),'unchangedSourceAndIrIdentical':unchanged['architecture']==original,'literalEdit':{'nodeId':refs[target['id']]['nodeId'],'parameter':'out_features','before':1,'after':2},'sourceFiles':len(original['sources']),'changedFiles':changed,'exactExpectedByteChange':True,'managedCopyReplayIdentical':replayed==result['architecture'],'generationScope':result['verification']['scope'],'noModelExecution':True,'structuralEditRejected':rejected,'originalReadonly':{'fileCount':len(after),'unchanged':before==after,'matchesPriorReadonlyEvaluation':after==old_manifest},'elapsedSeconds':round(time.monotonic()-t,3),'implementation':{str(path.relative_to(project)):hashlib.sha256(path.read_bytes()).hexdigest() for path in [project/'src/archcanvas_python/frontend.py',project/'src/archcanvas_python/discovery.py',project/'src/archcanvas_python/source_structure.py',project/'src/archcanvas_authoring/source_import.py',project/'src/archcanvas_authoring/source_preservation.py',project/'src/archcanvas_authoring/source_module_contracts.py',project/'src/archcanvas_python/rebind.py',project/'src/archcanvas_python/structural_rebind.py',project/'src/archcanvas_transactions/config_activation.py',project/'src/archcanvas_transactions/service.py',project/'studio/src/sourceEditingProjection.ts']}})
print(json.dumps(json.loads((evidence/'summary.json').read_text()), ensure_ascii=False,indent=2))
