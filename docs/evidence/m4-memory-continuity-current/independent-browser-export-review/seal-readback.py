"""Seal only this bounded review and its explicit current inputs."""
from pathlib import Path
import hashlib
import json
from datetime import datetime, timezone

OWNER=Path(__file__).resolve().parent
ROOT=OWNER.parents[3]
STAGE=OWNER.parent
def load(p):return json.loads(p.read_text())
def bind(p):
    p=Path(p)
    if not p.is_absolute():p=ROOT/p
    data=p.read_bytes()
    return {'path':str(p.relative_to(ROOT)),'bytes':len(data),'sha256':hashlib.sha256(data).hexdigest()}
def write(name,data):
    p=OWNER/name
    if p.exists():raise RuntimeError('Do not overwrite evidence: '+str(p))
    p.write_text(json.dumps(data,ensure_ascii=False,indent=2)+'\n')
report=load(OWNER/'readback-attempt-2/report.json')
first=load(OWNER/'readback-attempt-1/report.json')
script_binding=next(b for b in first['inputBindings'] if b['path'].endswith('/audit-readback.py'))
snapshot=bind(OWNER/'readback-attempt-1/audit-readback.py')
snapshot_exact=snapshot['sha256']==script_binding['sha256'] and snapshot['bytes']==script_binding['bytes']
if not snapshot_exact:raise RuntimeError('Historical script snapshot mismatch')
for attempt,passed,failed,inputs,exitcode in [('readback-attempt-1',2838,2,121,1),('readback-attempt-2',2840,0,124,0)]:
    write(attempt+'/execution-receipt.json',{
      'schema':'archcanvas-independent-command-output-transcription/1',
      'command':['.venv/bin/python','docs/evidence/m4-memory-continuity-current/independent-browser-export-review/audit-readback.py',attempt],
      'cwd':str(ROOT),'exitCode':exitcode,
      'returnedSummary':{'cases':19,'publicSvgCases':16,'relations':2840,'passed':passed,'failed':failed,'inputs':inputs,'inputsUnchanged':True},
      'report':str((OWNER/attempt/'report.json').relative_to(ROOT)),
      'scope':'Transcription of actual returned exec_command summary/exitCode in this session; not a rerun or an original terminal log. The failing first oracle script is separately preserved.'})
summary={
  'schema':'archcanvas-independent-browser-export-summary/1','createdUtc':datetime.now(timezone.utc).isoformat(),
  'report':bind(OWNER/'readback-attempt-2/report.json'),'cases':report['cases'],
  'browserRecords':17,'publicSvgCases':16,'relations':report['relations'],'passed':report['passed'],'failed':report['failed'],
  'currentInputBindings':len(report['inputBindings']),'inputsUnchanged':report['inputsUnchanged'],
  'preservedAttempt1':{'report':bind(OWNER/'readback-attempt-1/report.json'),'passed':2838,'total':2840,'failed':2,
                       'originalScriptSnapshotExact':snapshot_exact,'scriptSnapshot':snapshot,
                       'corrections':bind(OWNER/'oracle-corrections.json')},
  'actualDocumentsExact':sum(e['documentExact'] for e in report['exports']),
  'actualArtifacts':2,'canvasRevision':47,'storageRevision':7,'exports':report['exports'],
  'pdfCentrelines':12,'pdfMaximumCoordinateErrorPt':max(m['maxCoordinateErrorPt'] for r in report['pdfRoutes'] for m in r['matches']),
  'pdfCentrelineTolerancePt':0.0045,'pdfPageSizePt':[510.23622,590.416186],
  'physicalSvgRootMm':[180,208.28571],'preciseMetadataMm':[180,208.28571428571428],
  'rootObservation':bind(STAGE/'root-observation.json'),'pixelsViewedByThisReviewer':False,
  'firstPaintContinuityCertified':False,'servedAssetBytesVerified':False,
  'rootStaleRasterRecords':[2,4,10,16],'rootFiniteModalFreeFigureRecord':17,
  'humanParticipants':0,'M4':'partial','M5':'not_started','limits':report['limits']}
write('summary-final.json',summary)
paths={b['path'] for b in report['inputBindings']}
paths.update(str(p.relative_to(ROOT)) for p in OWNER.rglob('*') if p.is_file() and p.name not in ['manifest.json','seal-readback.json'])
bindings=[bind(p) for p in sorted(paths)]
write('manifest.json',{'schema':'archcanvas-independent-browser-export-material-manifest/1',
                       'scope':'Current explicit audit inputs plus every review evidence/script/output, excluding self and readback receipt. Sealed source/guard/frontier/adopt matrices untouched.',
                       'bindings':bindings})
manifest=bind(OWNER/'manifest.json')
after=[bind(b['path']) for b in bindings]
receipt={'schema':'archcanvas-independent-material-seal-readback/1','manifest':manifest,
         'rows':len(bindings),'passed':sum(b==a for b,a in zip(bindings,after)),
         'currentAuditInputs':len(report['inputBindings']),
         'currentAuditInputsExact':sum(bind(b['path'])==b for b in report['inputBindings']),
         'historicalAuditScriptSnapshotExact':snapshot_exact,
         'allCurrentMaterialExact':bindings==after,'humanParticipants':0,'M4':'partial','M5':'not_started'}
write('seal-readback.json',receipt)
print(json.dumps(receipt,ensure_ascii=False))
if not receipt['allCurrentMaterialExact'] or receipt['currentAuditInputsExact']!=receipt['currentAuditInputs']:
    raise SystemExit(1)
