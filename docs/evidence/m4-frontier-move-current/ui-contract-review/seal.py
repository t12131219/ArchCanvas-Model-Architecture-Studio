from pathlib import Path
import hashlib,json
from datetime import datetime,timezone

OWNER=Path(__file__).resolve().parent
ROOT=OWNER.parents[3]
def read(p):return json.loads(p.read_text())
def bind(p):
    p=Path(p)
    if not p.is_absolute():p=ROOT/p
    data=p.read_bytes()
    return {'path':str(p.relative_to(ROOT)),'bytes':len(data),'sha256':hashlib.sha256(data).hexdigest()}
def write(name,data):
    p=OWNER/name
    with p.open('x') as file:json.dump(data,file,ensure_ascii=False,indent=2);file.write('\n')
second=read(OWNER/'focused-attempt-2/receipt.json')
first=read(OWNER/'focused-attempt-1/receipt.json')
original=next(b for b in first['inputBindings'] if b['path']=='studio/tests/move-command-independent.test.ts')
snapshot=bind(OWNER/'focused-attempt-1/move-command-independent.test.ts')
exact=snapshot['sha256']==original['sha256'] and snapshot['bytes']==original['bytes']
if not exact:raise SystemExit('Original failing test snapshot differs')
current=sum(bind(b['path'])==b for b in second['inputBindings'])
if current!=len(second['inputBindings']):raise SystemExit('Focused inputs changed')
summary={'schema':'archcanvas-frontier-ui-command-independent-summary/1','createdUtc':datetime.now(timezone.utc).isoformat(),
         'focusedReceipt':bind(OWNER/'focused-attempt-2/receipt.json'),'tests':14,'passed':14,'failed':0,'skipped':0,'cancelled':0,
         'focusedExitCode':second['exitCode'],'inputRows':26,'currentInputsExact':current,'inputsUnchangedDuringRun':second['inputsUnchanged'],
         'originalFailingAttempt':{'receipt':bind(OWNER/'focused-attempt-1/receipt.json'),'passed':13,'failed':1,'originalTestSnapshot':snapshot,'originalTestSnapshotExact':exact},
         'oracleCorrection':bind(OWNER/'oracle-correction.json'),
         'actualCallbackNames':['cancelGesture','chooseMoveScope','apply','panInput','pointerDown','pointerMove','pointerUp','align','runCommand','previewPositionRecovery','applyPositionRecovery'],
         'scope':'Bounded literal parser, actual extracted App callback/state/capture/rAF contract and actual core cache/anchor preservation. Controlled harness, not mounted React or native browser paint. World canvas units, not CSS pixels.',
         'modelExecuted':False,'sourceWriteback':False,'browserManipulated':False,'humanParticipants':0,'M4':'partial','M5':'not_started',
         'limits':['Full suite/build are root-owned and separate','No human usability or researcher participation','No native event/paint/first-frame freshness or runtime UI pixel verification','No global aesthetics/publication/font/performance acceptance','Scope-specific caches retain operated-container/ancestor/pin switch constraints; all anchors across all hierarchy levels are not independent']}
write('summary-final.json',summary)
paths={b['path'] for b in second['inputBindings']}
paths.update(str(p.relative_to(ROOT)) for p in OWNER.rglob('*') if p.is_file() and p.name not in ['manifest.json','seal-readback.json'])
bindings=[bind(p) for p in sorted(paths)]
write('manifest.json',{'schema':'archcanvas-frontier-ui-command-independent-material/1','bindings':bindings,'scope':'Explicit current focused inputs and finite new independent evidence; no old material rewritten, self/readback excluded'})
after=[bind(b['path']) for b in bindings]
result={'schema':'archcanvas-frontier-ui-command-independent-seal-readback/1','manifest':bind(OWNER/'manifest.json'),
        'rows':len(bindings),'passed':sum(a==b for a,b in zip(after,bindings)),'allMaterialExact':after==bindings,
        'currentFocusedInputsExact':current,'currentFocusedInputsTotal':len(second['inputBindings']),
        'originalFailingTestSnapshotExact':exact,'humanParticipants':0,'M4':'partial','M5':'not_started'}
write('seal-readback.json',result)
print(json.dumps(result,ensure_ascii=False))
