"""Hash-only closure of new diagnostic review; older au3 closure remains immutable."""
from pathlib import Path
from datetime import datetime, timezone
import hashlib
import json

ROOT=Path(__file__).resolve().parents[5]
OUT=Path(__file__).resolve().parent
CACHE={}


def read(path):
    path=Path(path).absolute()
    raw=path.read_bytes()
    assert path not in CACHE or CACHE[path]==raw,path
    CACHE[path]=raw
    return raw


def bind(path,raw):
    return {'path':str(path.relative_to(ROOT)) if path.is_relative_to(ROOT) else str(path),
            'bytes':len(raw),'sha256':hashlib.sha256(raw).hexdigest()}


source=read(Path(__file__))
report_path=OUT/'reviewer-repair-attempt-3/report.json'
report=json.loads(read(report_path))
assert report['status']=='passed-with-stated-scope' and report['inputsUnchanged']
assert report['inputsBefore']==report['inputsAfter']
for record in report['inputsBefore']:
    raw=read(ROOT/record['path'])
    assert len(raw)==record['bytes'] and hashlib.sha256(raw).hexdigest()==record['sha256'],record['path']
supplemental=[]
for path in sorted(OUT.rglob('*')):
    if path.is_file():
        supplemental.append(bind(path,read(path)))
old_path=OUT.parent/'final-readback-attempt-2/receipt.json'
old_raw=read(old_path)
assert len(old_raw)==1265327 and hashlib.sha256(old_raw).hexdigest()=='545e75f1724df64a22dbc43f1a43fb44e8a2c91e5d0d78a9c69a56cd0607a832'
before=[bind(path,raw) for path,raw in sorted(CACHE.items())]
after=[bind(path,path.read_bytes()) for path in sorted(CACHE)]
assert before==after
receipt={'protocol':'archcanvas-au3-independent-input-diagnostic-final-readback/1',
         'finishedAt':datetime.now(timezone.utc).isoformat(),'status':'passed-with-stated-scope',
         'testsRun':False,'validatorRun':False,'modelsRun':False,'browserOperated':False,
         'oldMatrixRepeated':False,'oldFinalReceiptExact':bind(old_path,old_raw),
         'passedDiagnosticReport':bind(report_path,read(report_path)),
         'newDiagnosticInputBindingsRechecked':len(report['inputsBefore']),
         'supplementalFiles':supplemental,'auditorSource':bind(Path(__file__).absolute(),source),
         'inputsBefore':before,'inputsAfter':after,'inputsUnchanged':True,
         'limits':'Numerical matching/statistics and committed public DOM/source/context only. No native paint, human, full-page INP, hardware/font lock, performance pass, persistence or aesthetics certification. Old historical matrix UA/DPR unchanged.'}
raw=(json.dumps(receipt,ensure_ascii=False,indent=2)+'\n').encode()
(OUT/'final-readback.json').open('xb').write(raw)
print(json.dumps({'receipt':bind(OUT/'final-readback.json',raw),'inputs':len(CACHE),
                  'newDiagnosticBindings':len(report['inputsBefore']),'supplementalFiles':len(supplemental),
                  'oldFinalReceiptExact':True,'unchanged':True},ensure_ascii=False))
