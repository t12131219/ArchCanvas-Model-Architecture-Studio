"""Validate one documentation correction; execute only the existing Skill validator."""
from pathlib import Path
from datetime import datetime, timezone
from urllib.parse import unquote
import difflib
import hashlib
import json
import re
import subprocess

ROOT = Path(__file__).resolve().parents[3]
OUT = Path(__file__).resolve().parent
WORK = ROOT / 'docs/evidence/m4-authoring-interaction-work'
OLD_SEAL_PATH = ROOT / 'docs/evidence/m4-authoring-interaction-verification-sealed.json'
DOC_PATH = ROOT / 'docs/m4-completion.md'
ARCHIVE_PATH = OUT / 'before/docs/m4-completion.md'
SUPPLEMENT_PATH = OUT / 'seal-supplement.json'
RECEIPT_PATH = OUT / 'receipt.json'
seal = json.loads(OLD_SEAL_PATH.read_text())
old_doc_receipt = json.loads((WORK / 'doc-validation-attempt-2/receipt.json').read_text())
old_final_report_path = ROOT / 'docs/evidence/m4-authoring-interaction-final-readback-attempt-1/report.json'
old_finding_path = ROOT / 'docs/evidence/m4-authoring-interaction-final-readback-attempt-1/text-boundary-findings.md'
status_path = ROOT / 'docs/evidence/m4-human-review-handoff-status.json'
status = json.loads(status_path.read_text())
old_doc_binding = next(item for item in seal['records'] if item['path'] == 'docs/m4-completion.md')
expected_old_seal = {'path':str(OLD_SEAL_PATH.relative_to(ROOT)), 'bytes':254770,
                     'sha256':'332c05962c12a4d57f3d3cd1573178a19623c3498ef49123bb24746b9cc6af0d'}


def now():
    return datetime.now(timezone.utc).isoformat()


def resolve(path):
    candidate = Path(path)
    return candidate if candidate.is_absolute() else ROOT / candidate


def binding(path):
    data = path.read_bytes()
    return {'path':str(path.relative_to(ROOT)) if path.is_relative_to(ROOT) else str(path),
            'bytes':len(data),'sha256':hashlib.sha256(data).hexdigest()}


def exact(expected, actual):
    return expected['bytes'] == actual['bytes'] and expected['sha256'] == actual['sha256']


def dump_new(path, value):
    with path.open('x') as stream:
        json.dump(value,stream,ensure_ascii=False,indent=2)
        stream.write('\n')


paths = {OUT/'before-manifest.json', DOC_PATH, ARCHIVE_PATH, OLD_SEAL_PATH, status_path,
         old_final_report_path, old_finding_path, Path(__file__)}
paths.update(resolve(item['path']) for item in seal['records'])
paths.update(resolve(item['path']) for item in old_doc_receipt['documents'])
paths.update(resolve(item['path']) for item in status['evidenceRefs'])
validator = resolve(old_doc_receipt['skillValidator']['source']['path'])
paths.add(validator)
before = [binding(path) for path in sorted(paths)]
lookup = {item['path']:item for item in before}
records = []
for expected in seal['records']:
    target = ARCHIVE_PATH if expected['path'] == 'docs/m4-completion.md' else resolve(expected['path'])
    actual = binding(target)
    records.append({'expected':expected,'resolved':actual,'archived':target==ARCHIVE_PATH,'exact':exact(expected,actual)})
direct_changes = [{'expected':item,'actual':binding(resolve(item['path']))}
                  for item in seal['records'] if not exact(item,binding(resolve(item['path'])))]
documents = []
for expected in old_doc_receipt['documents']:
    actual = binding(resolve(expected['path']))
    documents.append({'prior':expected,'current':actual,'changed':not exact(expected,actual),
                      'expectedCorrection':expected['path']=='docs/m4-completion.md'})
status_refs = [{'expected':item,'actual':binding(resolve(item['path'])),
                'exact':item==binding(resolve(item['path']))} for item in status['evidenceRefs']]
old_bk = json.loads((ROOT / seal['priorBkSeal']['path']).read_text())
python_baseline = {item['path']:item for item in old_bk['records'] if item['path'].startswith('src/') and item['path'].endswith('.py')}
python_current_paths = sorted(path for path in (ROOT/'src').rglob('*.py') if '__pycache__' not in path.parts)
python_source_readback = [{'expected':python_baseline.get(str(path.relative_to(ROOT))), 'actual':binding(path),
                         'exact':str(path.relative_to(ROOT)) in python_baseline and exact(python_baseline[str(path.relative_to(ROOT))],binding(path))}
                        for path in python_current_paths]
before_doc = ARCHIVE_PATH.read_text()
after_doc = DOC_PATH.read_text()
old_row = '| M4-01–04 源码/holdout/shared/repeat/opaque | 静态子集有界 | 前端源码未由本次布局修复改变；历史证据只按原版本读取，不推广任意Python。 |'
new_row = '| M4-01–04 源码/holdout/shared/repeat/opaque | 静态子集有界 | 本轮未改动 Python 静态分析器与 backend 源码；Studio 的 authoring/UI/CSS/scene 呈现改动已作有界验证。历史静态证据只按原版本读取，不推广任意Python。 |'
correction_paragraph = '文档措辞纠正（2026-10-06）：上表此前“前端源码未改变”范围不明确，现限定为本轮未改动的 Python 静态分析器与 backend；Studio 改动仍按[端口交互阶段](m4-authoring-interaction.md)的有界结果读取。[纠正前原字节](evidence/m4-authoring-interaction-doc-correction-attempt-1/before/docs/m4-completion.md)保留旧封存绑定，[单文档纠正补充](evidence/m4-authoring-interaction-doc-correction-attempt-1/seal-supplement.json)记录唯一归档解析与新文档字节。旧[字节复读报告](evidence/m4-authoring-interaction-final-readback-attempt-1/report.json)与[语义发现](evidence/m4-authoring-interaction-final-readback-attempt-1/text-boundary-findings.md)保持原样；字节一致不代表全文无歧义。本纠正不改产品、旧seal或机器状态，不提高任何验收结论。'
roundtrip = after_doc.replace(new_row,old_row).replace('\n'+correction_paragraph+'\n','')
assert roundtrip == before_doc
diff_path = OUT/'document.diff'
with diff_path.open('x') as stream:
    stream.write(''.join(difflib.unified_diff(before_doc.splitlines(keepends=True),after_doc.splitlines(keepends=True),
                fromfile='archived/docs/m4-completion.md',tofile='current/docs/m4-completion.md')))
# This artifact contains the resolver/new document bindings. Its verification receipt
# is named by path to avoid a hash cycle; the receipt binds this supplement's bytes.
supplement = {
    'protocol':'archcanvas-single-current-doc-correction-seal-supplement/1','createdAt':now(),
    'scope':'One current M4 table wording clarification plus same-document explanation/links. All product, status, old seal/work/raw and previous final-readback bytes remain unchanged.',
    'oldSeal':binding(OLD_SEAL_PATH), 'oldSealExpected':expected_old_seal,
    'originalCurrentSealBindings':len(seal['records']),
    'soleDirectPathChange':'docs/m4-completion.md',
    'oldBindingResolution':[{'source':'docs/m4-completion.md','expected':old_doc_binding,'archive':binding(ARCHIVE_PATH)}],
    'currentDocument':binding(DOC_PATH),'beforeManifest':binding(OUT/'before-manifest.json'),
    'documentDiff':binding(diff_path),'validatorScript':binding(Path(__file__)),
    'priorFinalReadback':binding(old_final_report_path),'priorSemanticFinding':binding(old_finding_path),
    'old1071ResolvedExact':all(item['exact'] for item in records),
    'pythonAnalyzerBackendSourcesCompared':len(python_source_readback),
    'pythonAnalyzerBackendSourcesUnchanged':all(item['exact'] for item in python_source_readback),
    'validationReceipt':str(RECEIPT_PATH.relative_to(ROOT)),
    'independence':'The agent that reported the wording conflict made this authorized documentation correction and validates its own edit. This is not independent approval of the correction; root readback remains pending.',
    'rootIndependentReview':'pending','M4':'partial','M5':'not_started','humanParticipants':0,
    'productsTestsBuildModelsOrBrowserRun':False,'oldSealStatusRawOrProductEdited':False,
    'interpretation':'The original byte-pass report and semantic finding are retained without rewriting. Byte identity did not establish that every original sentence was unambiguous.'}
dump_new(SUPPLEMENT_PATH,supplement)
links = []
for item in documents:
    path = resolve(item['current']['path'])
    for match in re.finditer(r'\[[^\]\n]*\]\((<[^>]+>|[^\s)]+)(?:\s+"[^"]*")?\)',path.read_text()):
        raw=match.group(1).strip('<>');target=unquote(raw.split('#',1)[0])
        if not target or re.match(r'^[a-zA-Z][a-zA-Z0-9+.-]*:',target):
            continue
        resolved=Path(target) if target.startswith('/') else path.parent/target
        links.append({'document':item['current']['path'],'target':raw,'exists':resolved.exists()})
validator_copy = OUT/'quick_validate.py'
validator_copy.write_bytes(validator.read_bytes())
argv = [old_doc_receipt['skillValidator']['argv'][0],str(validator),'skills/archcanvas']
started = now()
run = subprocess.run(argv,cwd=ROOT,capture_output=True,check=False)
for name,data in [('skill.stdout.txt',run.stdout),('skill.stderr.txt',run.stderr)]:
    (OUT/name).write_bytes(data)
after = [binding(path) for path in sorted(paths)]
checks = {
    'oldSealOriginalSHAAndBytesUnchanged':binding(OLD_SEAL_PATH)==expected_old_seal,
    'exactOldDocArchivedBeforeEdit':exact(old_doc_binding,binding(ARCHIVE_PATH)),
    'onlyCurrentDocDirectBindingChanged':len(direct_changes)==1 and direct_changes[0]['expected']['path']=='docs/m4-completion.md',
    'all1071OldBindingsResolvedExactThroughSoleArchive':len(records)==1071 and all(item['exact'] for item in records),
    'docEditExactlyOneRowAndOneExplanation':roundtrip==before_doc,
    'python22AnalyzerBackendSourcesUnchanged':len(python_source_readback)==22 and all(item['exact'] for item in python_source_readback),
    'current15DocsOnlyCompletionChanged':len(documents)==15 and all(item['changed']==item['expectedCorrection'] for item in documents),
    'all461CurrentLocalLinksExist':len(links)==461 and all(item['exists'] for item in links),
    'status12And29RefsUnchangedExact':status['schemaVersion']==12 and len(status_refs)==29 and all(item['exact'] for item in status_refs) and binding(status_path)==lookup[str(status_path.relative_to(ROOT))],
    'SkillDocValidationExit0':run.returncode==0,
    'SkillValidatorMatchesPriorBoundSourceAndCopy':binding(validator)==old_doc_receipt['skillValidator']['source'] and binding(validator_copy)['sha256']==binding(validator)['sha256'],
    'previousFinalReportAndSemanticFindingUnchanged':binding(old_final_report_path)==lookup[str(old_final_report_path.relative_to(ROOT))] and binding(old_finding_path)==lookup[str(old_finding_path.relative_to(ROOT))],
    'validationInputsUnchanged':before==after,
    'M4StillPartialM5NotStartedHuman0':status['phaseStatus']=='partial' and status['nextPhaseStarted'] is False and status['humanResearch']['researchers']==0 and status['humanAcceptanceCertified'] is False,
}
receipt = {
    'protocol':'archcanvas-single-current-doc-correction-validation/1','startedAt':started,'finishedAt':now(),
    'pass':all(checks.values()),'checks':checks,'counts':{'validationInputs':len(before),'oldSealBindingsResolved':len(records),'soleArchivedResolution':1,'documents':len(documents),'localLinks':len(links),'statusRefs':len(status_refs),'pythonAnalyzerBackendSources':len(python_source_readback)},
    'inputsBefore':before,'inputsAfter':after,'old1071Readback':records,
    'soleDirectBindingChange':direct_changes,'documents':documents,'inlineLocalLinks':links,
    'statusReferences':status_refs,'pythonSourceReadback':python_source_readback,
    'skillValidator':{'argv':argv,'exitCode':run.returncode,'source':binding(validator),'copy':binding(validator_copy),'stdout':binding(OUT/'skill.stdout.txt'),'stderr':binding(OUT/'skill.stderr.txt'),'scope':'Existing instruction-package validator only; no product test/build/runtime/model/browser invocation.'},
    'sealSupplement':binding(SUPPLEMENT_PATH),
    'newArtifacts':[binding(path) for path in [OUT/'before-manifest.json',diff_path,SUPPLEMENT_PATH,Path(__file__)]],
    'independence':'Authorized correction and self-validation by mono_acceptance; root must independently review the final concrete artifacts.',
    'rootIndependentReview':'pending','oldSealStatusRawOrProductModified':False,'soleCurrentDocEdited':True,
    'productsTestsOrBuildRun':False,'modelsExecuted':False,'browserOperated':False,'dependenciesInstalled':False,
    'humanParticipants':0,'M4':'partial','M5':'not_started',
    'limits':['Old immutable seal retains the original document SHA; consumers must use this one-document archive resolver rather than pretending the corrected doc still has its old hash.',
              'Previous independent byte-pass and semantic-finding reports are historical exact originals, not rewritten to imply the wording was always correct.',
              'The Skill validation and local file links check documentation only. They do not certify product behavior, raster presentation, full aesthetics, human acceptance or a new release.',
              'This author corrected and validated the document; this receipt is not independent acceptance of its own prose.']}
dump_new(RECEIPT_PATH,receipt)
print(json.dumps({'receipt':binding(RECEIPT_PATH),'supplement':binding(SUPPLEMENT_PATH),'pass':receipt['pass'],'checks':checks,'counts':receipt['counts'],'currentDocument':binding(DOC_PATH)},ensure_ascii=False))
if not receipt['pass']:
    raise SystemExit(1)
