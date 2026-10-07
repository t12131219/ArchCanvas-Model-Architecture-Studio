"""Final independent read-only current/historical byte and receipt readback.

Preserved historical code is resolved only via separately frozen exact bytes;
an old package's intended version refusal is not mislabeled as byte damage.
This imports no product code and does not repeat product tests or browser input.
"""
from argparse import ArgumentParser
from datetime import datetime, timezone
import hashlib
import json
from pathlib import Path
import re
import subprocess

HERE = Path(__file__).resolve().parent
ROOT = HERE.parents[3]
STAGE = HERE.parent
MANIFESTS = {
    'before-change': 126,
    'self-route-review': 38,
    'independent-review/continuation-review': 1063,
    'export-integration-repair': 62,
    'browser-gesture-final': 140,
    'research-final-preparation': 547,
    'research-export-final-preparation': 566,
    'browser-caption-investigation': 102,
    'final-browser': 179,
    'browser-export-final': 221,
}

def bind(path):
    raw = path.read_bytes()
    return {'path': str(path.relative_to(ROOT)) if path.is_relative_to(ROOT) else str(path), 'bytes': len(raw), 'sha256': hashlib.sha256(raw).hexdigest()}

def load(path):
    return json.loads(path.read_bytes())

def main():
    parser = ArgumentParser(description=__doc__)
    parser.add_argument('--output', required=True, type=Path)
    parser.add_argument('--entry-verification', type=Path)
    parser.add_argument('--entry-manifest', type=Path)
    parser.add_argument('--browser-manifest', required=True, type=Path)
    args = parser.parse_args()
    for name in ['output', 'entry_verification', 'entry_manifest', 'browser_manifest']:
        value = getattr(args, name)
        if value is not None:
            setattr(args, name, (ROOT/value).resolve() if not value.is_absolute() else value.resolve())
    assert not args.output.exists(), 'No overwriting earlier readback attempts.'
    args.output.mkdir(parents=True)
    checks, relations, snapshots, inputs = [], [], {}, {}
    failures = []
    def check(name, condition):
        checks.append({'name': name, 'passed': bool(condition)})
        if not condition:
            failures.append(name)
    # These replacement candidates themselves have already sealed provenance.
    # Exact matching is still required for every historical binding resolution.
    for base in [STAGE/'before-change/inputs', STAGE/'export-integration-repair/before', STAGE/'export-integration-repair/after']:
        for path in base.rglob('*'):
            if path.is_file():
                row = bind(path)
                snapshots.setdefault((row['bytes'], row['sha256']), []).append(row['path'])
    def verify_row(row, label, current_only=False):
        path = ROOT / (row.get('snapshot', row['path']) if label == 'before-change' else row['path'])
        expected = {k: row[k] for k in ['bytes', 'sha256']}
        direct = path.is_file() and all(bind(path)[k] == expected[k] for k in expected)
        retained = [] if current_only or direct else snapshots.get((row['bytes'], row['sha256']), [])
        check(label + ' exact bytes ' + row['path'], direct or bool(retained))
        resolved = bind(path)['path'] if direct else retained[0] if retained else None
        relations.append({'scope': label, 'logicalPath': row['path'], 'bytes': row['bytes'], 'sha256': row['sha256'],
                          'resolvedPath': resolved, 'directAtOriginalPath': direct, 'retainedHistoricalSnapshot': bool(retained)})
        if resolved:
            inputs[resolved] = bind(ROOT/resolved)
    manifest_summaries = []
    frozen_inventory=load(HERE/'before-final-readback-inputs.json')
    for row in frozen_inventory['inputs']:
        verify_row(row,'pre-final frozen seal/log inventory',current_only=True)
    for name, count in MANIFESTS.items():
        path = STAGE/name/'manifest.json'
        inputs[str(path.relative_to(ROOT))] = bind(path)
        manifest = load(path)
        rows = manifest.get('inputs', [])+manifest.get('artifacts', [])+manifest.get('externalInputs', [])+manifest.get('externalBindings', [])
        check(name+' expected sealed row count', len(rows) == count)
        for row in rows:
            verify_row(row, name, current_only=name=='research-export-final-preparation')
        manifest_summaries.append({'name':name,'binding':bind(path),'rows':len(rows),'expectedRows':count})
    receipt_path = STAGE/'checks-final-attempt-4/receipt.json'
    receipt = load(receipt_path)
    check('checks4 inventory105source3dist11publication', len(receipt['inputs']) == 105 and len(receipt['build']) == 3 and len(receipt['publicationInputs']) == 11)
    check('checks4 all exited0 unchanged scoped inputs', receipt['inputsUnchanged'] and receipt['publicationInputsUnchanged'] and all(x['exitCode'] == 0 for x in receipt['checks']))
    for group in ['inputs','build','publicationInputs']:
        for row in receipt[group]:
            verify_row(row, 'current checks4 '+group, current_only=True)
            if 'snapshot' in row:
                verify_row({**row,'path':row['snapshot'],'snapshot':row['snapshot']}, 'checks4 dist snapshot', current_only=True)
    studio_log=(STAGE/'checks-final-attempt-4/studio.txt').read_text()
    pub_log=(STAGE/'checks-final-attempt-4/publication.txt').read_text()
    check('actual Studio389 pass0fail0skip0cancel', all(re.search(r'^ℹ '+label+' '+str(n)+r'$',studio_log,re.M)for label,n in [('tests',389),('pass',389),('fail',0),('skipped',0),('cancelled',0)]))
    check('actual publication11 pass no skip', len(re.findall(r' \.\.\. ok$',pub_log,re.M)) == 11 and 'Ran 11 tests in' in pub_log and pub_log.rstrip().endswith('OK') and 'skipped' not in pub_log)
    # All old product/checker failures remain exact artifacts or explicitly frozen
    # historical logs. Their contents are preserved; they are not passing claims.
    for folder in ['checks-final-attempt-1','checks-final-attempt-2','checks-final-attempt-3','checks-final-attempt-4']:
        for path in sorted((STAGE/folder).rglob('*')):
            if path.is_file():
                inputs[str(path.relative_to(ROOT))] = bind(path)
    browser_manifest=load(args.browser_manifest)
    browser_rows=browser_manifest.get('artifacts',[])+browser_manifest.get('externalInputs',[])+browser_manifest.get('externalBindings',[])+browser_manifest.get('inputs',[])
    check('browser final manifest has actual artifacts', bool(browser_rows))
    for row in browser_rows:
        verify_row(row,'root browser final',current_only=True)
    inputs[str(args.browser_manifest.relative_to(ROOT))] = bind(args.browser_manifest)
    browser_receipt=load(STAGE/'final-browser/receipt.json')
    old_envelope=load(STAGE/'browser/pre-ui/saved-transformer-envelope.json')
    final_envelope=load(STAGE/'browser/pre-ui/saved-transformer-final-envelope.json')
    old_document, final_document=old_envelope['document'], final_envelope['document']
    check('actual final stored document changes only revision0to20',set(old_document)==set(final_document) and
          [k for k in old_document if old_document[k]!=final_document[k]]==['revision'] and old_document['revision']==0 and final_document['revision']==20)
    check('actual final storagecounter1to3 agrees with rootreceipt',old_envelope['revision']==browser_receipt['initialStorageCounter']==1 and final_envelope['revision']==browser_receipt['finalStorageCounter']==3 and browser_receipt['finalDocumentRevision']==final_document['revision'])
    export_report=load(STAGE/'browser-export-final/report.json')
    check('independent actual export178 relations passed',export_report['relationCount']==178 and not export_report['failedRelations'])
    actual_exports=[]
    for export_directory in sorted((STAGE/'browser-export-final/exports').iterdir()):
        if export_directory.is_dir():
            actual_export=load(export_directory/'document.json')
            check('actual final UI exportdocument matches stored20 '+export_directory.name,actual_export==final_document)
            actual_exports.append(export_directory.name)
    check('all3 declared actualUI exports present',set(actual_exports)=={row['id']for row in browser_receipt['actualUiExports']} and len(actual_exports)==3)
    check('browser known gap/camera/performance/human limitations remain explicit',browser_receipt['unresolvedExperienceGap']['memoryLabelAndGuideDisappear'] and
          not browser_receipt['cameraPreservedAfterReload'] and not browser_receipt['continuousInputPerformanceCertified'] and not browser_receipt['presentedFpsCertified'] and
          not browser_receipt['physicalPublicationApproved'] and browser_receipt['humanParticipants']==0)
    if args.entry_verification:
        entries=load(args.entry_verification)
        check('independent final entry/history/link verifier passed', entries['passed'] == entries['total'] and entries['total'] > 100 and all(x['passed']for x in entries['checks']))
        check('entry link/current-input scopes exist', bool(entries['markdownLinks']) and bool(entries['gateLinks']) and bool(entries['currentInputs']))
        for row in entries['currentInputs']:
            verify_row(row,'actual current entries',current_only=True)
        inputs[str(args.entry_verification.relative_to(ROOT))] = bind(args.entry_verification)
        entry_directory=args.entry_verification.parent
        skill_process=load(entry_directory/'skill-validation-attempt-2.process.json')
        diff_process=load(entry_directory/'scoped-diff-check-attempt-2.process.json')
        check('actual final Skill validator exited0',skill_process['exitCode']==0)
        check('actual final scoped documentation diff check exited0',diff_process['exitCode']==0)
        for name in ['skill-validation-attempt-2.process.json','scoped-diff-check-attempt-2.process.json']:
            path=entry_directory/name
            inputs[str(path.relative_to(ROOT))]=bind(path)
    if args.entry_manifest:
        entry_seal=load(args.entry_manifest)
        entry_rows=entry_seal.get('artifacts',[])+entry_seal.get('externalInputs',[])+entry_seal.get('externalBindings',[])+entry_seal.get('inputs',[])
        check('final entryupdate sealed artifact inventory exists',bool(entry_rows))
        for row in entry_rows:
            verify_row(row,'sealed final entries',current_only=True)
        inputs[str(args.entry_manifest.relative_to(ROOT))]=bind(args.entry_manifest)
    current=ROOT/'.archcanvas/m4-research-trial-caption-route-export-current'
    current_manifest=load(current/'manifest.json')
    check('current research zerohumans five unused43571to43575',current_manifest['researcherCount']==0 and current_manifest['researchGate']=='not_run' and
          [s['port']for s in current_manifest['slots']]==[43571,43572,43573,43574,43575] and all(s['participantCode']is None and s['assignment']=='unassigned'for s in current_manifest['slots']))
    for row in current_manifest['implementationFiles']:
        verify_row(row,'current research implementation',current_only=True)
    for row in current_manifest['baseline']['files']:
        verify_row({**row,'path':str(current.relative_to(ROOT))+'/'+row['path']},'current research baseline',current_only=True)
    # The official current verify remains useful for runtime contract only;
    # independent byte checks above prove the actual inventory separately.
    command=[str(ROOT/'.venv/bin/python'),'scripts/research_trial.py','verify','--package',str(current)]
    result=subprocess.run(command,cwd=ROOT,capture_output=True,text=True)
    (args.output/'current-package-verify.stdout.json').write_text(result.stdout)
    (args.output/'current-package-verify.stderr.txt').write_text(result.stderr)
    check('actual current formal package verify exit0',result.returncode==0)
    report={'schema':'archcanvas-caption-route-final-independent-readback/1','createdUtc':datetime.now(timezone.utc).isoformat(),
            'status':'passed-current-historical-readback'if not failures else'failed-readback','passed':sum(c['passed']for c in checks),'total':len(checks),
            'checks':checks,'failures':failures,'bindingRelations':relations,'sealedManifests':manifest_summaries,'currentSourceBuildBindings':108,'currentPublicationInputBindings':11,
            'entryVerification':bind(args.entry_verification)if args.entry_verification else None,'entryVerificationPending':args.entry_verification is None,
            'entryManifest':bind(args.entry_manifest)if args.entry_manifest else None,
            'browserFinalManifest':bind(args.browser_manifest),'officialCurrentVerify':{'command':command,'exitCode':result.returncode},
            'resolvedInputs':list(inputs.values()),'limits':['Byte/readiness/documentation verification is not native-input, continuous gesture, presented FPS, physical publication or human acceptance.',
              'Historical research1 references old exporter/test bytes resolved through sealed before snapshots; their intended stale implementation refusal is not a frozen-package byte failure.']}
    (args.output/'report.json').write_text(json.dumps(report,ensure_ascii=False,indent=2)+'\n')
    print(json.dumps({'status':report['status'],'passed':report['passed'],'total':report['total'],'failures':failures,'bindingRows':len(relations),'exactResolvedInputs':len(inputs)}))
    raise SystemExit(0 if not failures else 1)

if __name__=='__main__':
    main()
