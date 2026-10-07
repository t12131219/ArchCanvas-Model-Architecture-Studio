from pathlib import Path
import hashlib,json
from datetime import datetime,timezone

OWNER=Path(__file__).resolve().parent
ROOT=OWNER.parents[3]
def bind(p):
    p=Path(p)
    if not p.is_absolute(): p=ROOT/p
    data=p.read_bytes()
    return {'path':str(p.relative_to(ROOT)),'bytes':len(data),'sha256':hashlib.sha256(data).hexdigest()}
def write(name,data):
    with (OWNER/name).open('x') as f:
        json.dump(data,f,ensure_ascii=False,indent=2)
        f.write('\n')
report=json.loads((OWNER/'focused-attempt-1/report.json').read_text())
summary={'schema':'archcanvas-frontier-ui-command-final-summary/1','createdUtc':datetime.now(timezone.utc).isoformat(),
 'report':bind(OWNER/'focused-attempt-1/report.json'),'tests':14,'passed':14,'failed':0,'skipped':0,'cancelled':0,
 'exitCode':report['exitCode'],'inputRows':len(report['inputBindings']),'inputsUnchanged':report['inputsUnchanged'],
 'iterationReview':report['iterationReview'],'rootChecks':report['rootChecks'],
 'priorFocusedMaterial':'docs/evidence/m4-frontier-move-current/ui-contract-review',
 'scope':report['scope'],'humanParticipants':0,'M4':'partial','M5':'not_started'}
write('summary-final.json',summary)
paths={b['path'] for b in report['inputBindings']}
paths.update(str(p.relative_to(ROOT)) for p in OWNER.rglob('*') if p.is_file() and p.name not in ['manifest.json','seal-readback.json'])
bindings=[bind(p) for p in sorted(paths)]
write('manifest.json',{'schema':'archcanvas-frontier-ui-command-final-material/1','bindings':bindings,
 'scope':'Current final focused report, source/log bindings and root-check references; excludes self/readback and preserves earlier review.'})
after=[bind(b['path']) for b in bindings]
result={'schema':'archcanvas-frontier-ui-command-final-seal/1','manifest':bind(OWNER/'manifest.json'),
 'rows':len(bindings),'passed':sum(x==y for x,y in zip(bindings,after)),'allMaterialExact':bindings==after,
 'focusedInputsExact':sum(bind(b['path'])==b for b in report['inputBindings']),'focusedInputsTotal':len(report['inputBindings']),
 'priorTestSnapshotExact':report['iterationReview']['priorFocusedTestSnapshotExact'],
 'onlyIterationTypeCorrection':report['iterationReview']['onlyLiteralIterationTypeExpressionReplacement'],
 'humanParticipants':0,'M4':'partial','M5':'not_started'}
write('seal-readback.json',result)
print(json.dumps(result,ensure_ascii=False))
