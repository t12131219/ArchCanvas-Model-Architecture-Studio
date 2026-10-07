"""Read-only current-document/evidence audit; writes only this attempt directory."""
from pathlib import Path
import datetime
import hashlib
import json

ROOT = Path(__file__).resolve().parents[4]
OUT = Path(__file__).resolve().parent
BASE = 'docs/evidence/m4-au3-visual-matrix-work/'
started = datetime.datetime.now(datetime.timezone.utc).isoformat()
inputs = {}
groups = {}


def path(value):
    p = Path(value)
    return p if p.is_absolute() else ROOT / p


def record(value):
    p = path(value)
    b = p.read_bytes()
    name = str(p.relative_to(ROOT)) if p.is_relative_to(ROOT) else str(p)
    actual = {'path': name, 'bytes': len(b), 'sha256': hashlib.sha256(b).hexdigest()}
    inputs.setdefault(name, actual)
    return actual


def load(value):
    record(value)
    return json.loads(path(value).read_text())


def checked_refs(name, refs):
    results = []
    for expected in refs:
        actual = record(expected['path'])
        match = actual['sha256'] == expected['sha256']
        if 'bytes' in expected:
            match = match and actual['bytes'] == expected['bytes']
        results.append({'expected': expected, 'actual': actual, 'matches': match})
    groups[name] = {'count': len(results), 'allMatch': all(x['matches'] for x in results), 'results': results}
    return groups[name]['allMatch']


mutation = load(BASE + 'docs-finalize-attempt-1/mutation-receipt.json')
repair = load(BASE + 'docs-release-scope-repair-attempt-1.json')
ancestor_scope = load(BASE + 'ancestor-report-time-scope-attempt-1.json')
link1 = load(BASE + 'status-validation-link-attempt-1.json')
link2 = load(BASE + 'status-independent-input-link-attempt-1.json')
status_path = 'docs/evidence/m4-human-review-handoff-status.json'
status = load(status_path)
collection = load(BASE + 'collection-attempt-1/attempt-receipt.json')
matrix = load('docs/evidence/browser-visual-matrix-au3-current/manifest.json')
independent = load(BASE + 'independent-audit/final-readback-attempt-2/receipt.json')
fit = load(BASE + 'pixel-audit/all-36-fit.receipt.json')
local = load(BASE + 'pixel-audit/gestures/three-model-local-and-edited.receipt.json')
skill = load(BASE + 'docs-finalize-attempt-1/skill-validation.json')
validator = load(BASE + 'input-diagnostic/validation-attempt-1/command-receipt.json')
diagnostic = load(BASE + 'input-diagnostic/validation-attempt-1/stdout.json')
input_review = load(BASE + 'independent-audit/input-diagnostic-attempt1/final-readback.json')
archive = load('docs/evidence/before-m4-au3-full-matrix/manifest.json')
standalone = load(status['tests']['standalone']['scopeReview'])
studio = load(status['tests']['studio']['receipt'])
build = load(status['tests']['buildReceipt'])

checked_refs('statusEvidenceReferences', status['evidenceRefs'])
checked_refs('currentValidatedSkillFiles', skill['skillFilesAfter'])
checked_refs('unchangedCollectionProductInputs', collection['sourceBuildBefore'])
checked_refs('studioTestReceiptSources', studio['bindings'])
checked_refs('buildReceiptSources', build['bindings'])
checked_refs('studioAndBuildFrozenLogs', studio['logs'] + build['logs'])
checked_refs('preservedLocalRawFiles', local['boundUniqueRawFiles'])
checked_refs('inputValidatorInputsOutputs', validator['inputs'] + validator['outputs'])
checked_refs('currentSkillValidatorImplementation', [skill['validator']])
fit_raw = []
fit_review_refs = []
for entry in fit['entries']:
    review = load(entry['reviewFile'])
    fit_review_refs.append({'path': entry['reviewFile'], 'sha256': entry['sha256']})
    fit_raw.extend(review['sourceFiles'])
checked_refs('preservedFitReviewFiles', fit_review_refs)
checked_refs('preservedFitRawFiles', fit_raw)

doc_paths = [r['path'] for r in mutation['after']]
doc_paths += ['docs/m4-au3-current-matrix.md', BASE + 'README.md', 'docs/m4-ancestor-corridors.md']
docs = {}
snapshots = []
for name in doc_paths:
    actual = record(name)
    b = path(name).read_bytes()
    docs[name] = b.decode()
    target = OUT / 'snapshots' / name
    target.parent.mkdir(parents=True, exist_ok=True)
    with target.open('xb') as f:
        f.write(b)
    snapshots.append({'source': actual, 'snapshot': record(target)})

record('AGENTS.md')
record('skills/archcanvas/SKILL.md')
plan_path = ROOT.parent / 'ArchCanvas_双向模型可视化与编辑框架_技术计划书.md'
plan = plan_path.read_text()
record(plan_path)
initial = record(OUT / 'initial-findings.json')

expected_after = {r['path']: r for r in mutation['after']}
for change in repair['changes']:
    expected_after[change['path']] = {'path': change['path'], **change['after']}
expected_after[status_path] = {'path': status_path, **link2['after']}
expected_after[ancestor_scope['path']] = {'path': ancestor_scope['path'], **ancestor_scope['after']}
checked_refs('currentDocsAfterRecordedRepairsAndLinks', list(expected_after.values()))
mutation_after_status = next(r for r in mutation['after'] if r['path'] == status_path)
status_chain = ({k: mutation_after_status[k] for k in ['bytes', 'sha256']} == link1['before']
                and link1['after'] == link2['before']
                and record(status_path) == {'path': status_path, **link2['after']})
repair_before_exact = all(change['before'] == {k: next(r for r in mutation['after'] if r['path'] == change['path'])[k]
                                              for k in ['bytes', 'sha256']} for change in repair['changes'])


def witnesses(name, fragments):
    lines = docs[name].splitlines()
    return [{'path': name, 'line': i + 1, 'text': line}
            for fragment in fragments for i, line in enumerate(lines) if fragment in line]


checks = []


def check(name, passed, conclusion, evidence=None):
    checks.append({'check': name, 'passed': bool(passed), 'conclusion': conclusion,
                   'documentWitnesses': evidence or []})


current_doc = docs['docs/m4-au3-current-matrix.md']
chinese_headers = [r['path'] for r in mutation['after'] if r['path'].endswith('.md')
                   and r['path'] not in ['docs/m4-au3-current-matrix.md', BASE + 'README.md']
                   and not r['path'].startswith('skills/')]
check('Current headers scope historical paragraphs', all('au3' in docs[name].splitlines()[2]
      and 'M4 partial' in docs[name].splitlines()[2]
      and ('历史' in docs[name].splitlines()[2] or '冻结时点' in docs[name].splitlines()[2])
      for name in chinese_headers),
      'All 15 changed Chinese document current headers identify au3, M4 partial and historical scope. Historical current/final words are not inherited as current evidence.')
ancestor_map = next(x for x in archive['mapping'] if x['sourcePath'] == ancestor_scope['path'])
old_ancestor_path = 'docs/evidence/before-m4-au3-full-matrix/' + ancestor_map['archivePath']
checked_refs('ancestorOriginalArchivedBytes', [{'path': old_ancestor_path, **ancestor_scope['before']}])
old_ancestor = path(old_ancestor_path).read_text()
ancestor_text = docs[ancestor_scope['path']]
new_scope_paragraph = ancestor_text.splitlines()[2]
check('Same-build ancestor report original frozen-time scope',
      all(x in new_scope_paragraph for x in ['冻结时点', '随后已完成新的39例矩阵', '三模型四向', 'm4-au3-current-matrix.md'])
      and ancestor_text.replace(new_scope_paragraph + '\n\n', '', 1) == old_ancestor
      and ancestor_scope['before'] == {k: ancestor_map[k] for k in ['bytes', 'sha256']},
      'Ancestor implementation report now links the later same-au3 collection and limits its old incomplete-browser statements to the original frozen time. Removing only that added scope paragraph reconstructs the exact archived original; old paragraphs are preserved.',
      witnesses(ancestor_scope['path'], ['本页保留祖先侧路由']))
check('Repair and mutable status transition provenance', repair_before_exact and status_chain,
      'Repair before hashes match the initial mutation receipt. Current status follows both separately recorded link updates; the initial status mutation hash is not presented as the final status hash.')
rows = witnesses('docs/m4-completion.md', ['| 当前产品回归 |']) + witnesses('docs/m4-human-review-handoff.md', ['| 当前au3产品回归 |'])
check('Repaired release rows retain proper scope', len(rows) == 2 and all('两份Skill reference后改' in x['text']
      and '非当前全发行字节' in x['text'] for x in rows)
      and status['tests']['standalone']['currentFullReleaseFilesStillExact'] is False
      and status['tests']['standalone']['laterSkillReferenceEdits'] is True
      and standalone['allNineChecksExact'] is True
      and [standalone['sourceFilesBound'], standalone['dependencyFilesBound'], standalone['dependencySymlinksBound']] == [209, 654, 5],
      'Frozen release copy had 9/9 checks and 209 source/654 dependency/5 symlink inputs in its own run. Current product inputs remain exact; two later Skill reference edits prevent current whole-release byte certification or clean-install claims.', rows)
check('Artifact matrix counts and acceptance split',
      [collection['caseCount'], collection['baselineCount'], collection['editedCount']] == [39, 36, 3]
      and len(matrix['captures']) == 39 and len(matrix['variants']) == 36
      and status['currentBrowser']['authoredFrontiers'] == 9
      and status['currentBrowser']['captureFiles'] == 234
      and collection['artifactCoverage'] == 'complete'
      and matrix['visualAcceptance'] == 'pending-human-review'
      and independent['matrix']['artifactBindings'] == 234
      and matrix['humanAcceptanceCertified'] is False,
      'Nine real frontiers with two presets and two widths form 36 baseline configurations, plus three edited cases. File coverage does not certify aesthetics or humans.',
      witnesses('docs/m4-au3-current-matrix.md', ['形成 36 基线', 'artifactCoverage=complete']))
check('Export-only first case and finite metadata tail tolerance',
      status['currentBrowser']['firstCaseExportOnly'] == 'transformer-level0-paper-180'
      and status['currentBrowser']['storedSnapshotCases'] == 38
      and status['currentBrowser']['heightMmOnlyToleranceCases'] == len(fit['metadataExactMismatchCases']) == 6
      and status['currentBrowser']['heightMmTolerance'] == 1e-10
      and 'storageRevision 为 null' in current_doc and 'SVG 原字节' in current_doc,
      'The first case lacks a frozen saved envelope, and six derived heightMm serialization tails use a finite 1e-10 tolerance while SVG bytes remain exact.',
      witnesses('docs/m4-au3-current-matrix.md', ['首例 Transformer', 'heightMm']))
check('Matrix environment provenance not retroactively strengthened',
      'UA/DPR 明示沿用同 IAB 的历史观测' in current_doc
      and '仍不倒填矩阵为同刻采集' in current_doc
      and status['currentInputDiagnostic']['currentUaDprObserved'] is True
      and status['currentInputDiagnostic']['resolvedFontsHardwareCertified'] is False,
      'Current matrix DOM viewport/camera/assets and historical same-IAB UA/DPR remain separate. Later current UA/DPR observation does not backfill matrix or resolved fonts/hardware.',
      witnesses('docs/m4-au3-current-matrix.md', ['UA/DPR']))
check('Four-direction operation scope', status['currentBrowser']['fourDirectionOperations'] == 12
      and '各 24 CSS px' in current_doc and '±32' in current_doc and '±28' in current_doc
      and '已有非空 pins' in current_doc and '按住期间 Escape 取消' in current_doc,
      'Actual small leaf moves, history and persistence cover 12 model/direction combinations. Arbitrary objects/deltas, ancestor moves, nonempty pins and held cancellation are not certified.',
      witnesses('docs/m4-au3-current-matrix.md', ['共 12 个方向']))
check('Pixel mismatch and separate retry remain explicit',
      fit['reviewedOriginalWholeWindowScreenshots'] == 36
      and local['reviewCount'] == 19 and local['matchedImageStates'] == 18 and local['mismatchImageStates'] == 1
      and local['retryScope']['originWorldY'] == 648 and local['retryScope']['moveDocumentRevision'] == 36
      and local['retryScope']['replacesOldEvidence'] is False and local['retryScope']['originScreenshotExists'] is False
      and 'rev22/X138' in current_doc and 'rev23/X142' in current_doc and 'rev36/X142' in current_doc,
      '36 fit images and 19 local/edited images are AI review only. One original MLP right image remains mismatched; the new Y648 retry is separate and has no origin JPEG.',
      witnesses('docs/m4-au3-current-matrix.md', ['36 张 fit 图', '局部及编辑后审查']))
check('Remaining visual defects and physical limits retained',
      len(status['currentBrowser']['retainedVisualIssues']) == 4
      and status['currentBrowser']['publicationCertified'] is False
      and status['currentBrowser']['globalRouteBeautyCertified'] is False
      and all(s in current_doc for s in ['扁 U 外绕', '短阶梯折角', '6 世界单位窄缝', '下跳 566 世界单位', '14–26%']),
      'CNN external residual detour and close gaps, MLP stair alignment and Transformer route instability remain concrete findings. Deep fit review does not certify glyphs/arrowheads or physical publication.',
      witnesses('docs/m4-au3-current-matrix.md', ['扁 U 外绕', '短阶梯折角', '6 世界单位窄缝', '下跳 566 世界单位']))
lat = diagnostic['latency']
di = status['currentInputDiagnostic']
check('Full observer denominator and numbers',
      len(diagnostic['trials']) == di['attempts'] == 6
      and sum(x.get('operationSucceeded', False) for x in diagnostic['trials']) == di['completedOperations'] == 5
      and diagnostic['trials'][0]['status'] == 'no-input'
      and [lat['eligibleDiscreteInputs'], lat['matchedDiscreteInputs'], lat['matchedInteractions'], lat['matchedInteractionP95Ms']] == [14, 10, 4, 3000]
      and [di['eligibleDiscreteInputs'], di['matchedDiscreteInputs'], di['matchedInteractions'], di['matchedSubsetP95Ms']] == [14, 10, 4, 3000]
      and di['rafCadenceFps'] == diagnostic['frameCadence']['fps']
      and di['idleRafCadenceFps'] == diagnostic['idleCadence']['fps']
      and validator['exitCode'] == 0 and diagnostic['completeBuffers'] is True
      and diagnostic['dropped'] == diagnostic['errors'] == [],
      'Six attempts include one no-input and five completed operations. Eligible14/matched10/four interactions, matched-subset p95 3000ms, complete buffers and empty errors/dropped agree with frozen validator stdout.',
      witnesses('docs/m4-au3-current-matrix.md', ['合计六次尝试', 'matched-subset p95']))
check('Engineering cadence and DOM proxy not presentation performance',
      di['renderedExpandedObjects'] == 304 and di['allObjectsSimultaneouslyInViewportCertified'] is False
      and di['presentedPerformanceCertified'] is False and di['overallInpCertified'] is False
      and di['activeCancellationCertified'] is False
      and input_review['validatorRun'] is False and input_review['oldMatrixRepeated'] is False
      and '304 rendered 对象不表示' in current_doc and '非因果 paint 代理' in current_doc
      and 'fonts.status=loaded' in current_doc and 'loadedFaces=[]' in current_doc,
      '304 rendered nodes do not mean simultaneous viewport visibility. rAF callback cadence and noncausal input-to-DOM proxies do not certify presentation, whole-page INP, resolved fonts or held cancellation. Independent input review did not rerun validator or matrix.',
      witnesses('docs/m4-au3-current-matrix.md', ['304 rendered', '非因果 paint 代理', 'loadedFaces=[]']))
check('Beta numerical target provenance', '18.5' in plan and 'p95' in plan and '50' in plan
      and '初始 Beta 目标' in current_doc and 'M4 新硬门' in current_doc,
      'Plan §18.5 Beta targets remain targets; no new M4 numeric hard gate or performance pass is invented.',
      witnesses('docs/m4-au3-current-matrix.md', ['计划书 §18.5']))
research = status['research']
check('Current research remains unprepared and human0',
      research['currentAu3PackagePrepared'] is False and research['currentAu3PackageVerified'] is False
      and [research['assignedCount'], research['collectedCount'], research['humanResearcherCount']] == [0, 0, 0]
      and research['oldSlotsMayBeAssigned'] is False and research['aiCountsAsHuman'] is False
      and research['taskDenominatorSeconds'] == 180
      and status['phaseStatus'] == 'partial' and status['nextPhaseStarted'] is False
      and status['humanAcceptanceCertified'] is False,
      'AI tasks do not become real researcher records. Current au3 research package is not prepared/verified, stale slots cannot be assigned, the five-step denominator remains180s, M4 partial and M5 not started.',
      witnesses('docs/m4-au3-current-matrix.md', ['AI 不计作真人', '真人分配/记录为 0']))
check('Authored catalog and prior chain coverage remain bounded',
      status['previousBoundedBrowser']['authoredDraft']['nodes'] == 4
      and status['previousBoundedBrowser']['authoredDraft']['edges'] == 3
      and status['previousBoundedBrowser']['authoredDraft']['modelExecuted'] is False
      and status['historicalAiSmokeThisRound']['individualModuleClickAdds'] == 17
      and status['historicalAiSmokeThisRound']['staleForCurrentAu3'] is True
      and '17 基础模块与 3 透明组合起点' in current_doc
      and '逐模块参数/生成' in current_doc,
      'The au3 four-node/three-edge authored chain remains separately bound. 17 base modules and three transparent starting graphs do not certify current per-module parameters/generation, Attention/sequence support or human novice success.',
      witnesses('docs/m4-au3-current-matrix.md', ['已有 au3 的 Input', '17 基础模块']))
studio_log = path(studio['logs'][0]['path']).read_text()
build_log = path(build['logs'][0]['path']).read_text()
check('Regression claims retain source/version scope',
      studio['exitCode'] == build['exitCode'] == 0 and 'tests 179' in studio_log and 'pass 179' in studio_log
      and 'fail 0' in studio_log and 'skipped 0' in studio_log and 'tsc --noEmit && vite build' in build_log
      and 'index-au3IB_0Q.js' in build_log and status['tests']['suiteCountsCombined'] is False
      and status['tests']['rerunThisCollectionRound'] is False
      and skill['exitCode'] == 0 and skill['skillFilesBefore'] == skill['skillFilesAfter'],
      'Current source-bound179/179 and strict/build receipts are retained; separate26/26 is not added. Current host Skill validation is7 unchanged files and is not runtime/browser testing. This audit reruns none of them.', rows)
check('Historical archive count and frozen receipts preserved',
      archive['contentFileCount'] == len(archive['mapping']) == 4259
      and [archive['sealBindingCount'], archive['supplementalBindingCount'], archive['addedSelfExcludedFiles']] == [4233, 24, 2]
      and status['historicalArchive']['files'] == 4259
      and independent['inputsUnchanged'] is True and input_review['inputsUnchanged'] is True
      and input_review['oldFinalReceiptExact']['sha256'] == record(BASE + 'independent-audit/final-readback-attempt-2/receipt.json')['sha256'],
      'Current headers agree with4259 archival content files:4233 prior seal bindings,24 supplemental and two original receipts. Frozen matrix/pixel/input audit receipts remain byte-bound; this audit does not rewrite them or rerun full archive collection.')

source_record = record(__file__)
before = [inputs[k] for k in sorted(inputs)]
after = []
for item in before:
    after.append(record(item['path']))
inputs_unchanged = before == after
passed = all(c['passed'] for c in checks) and all(g['allMatch'] for g in groups.values()) and inputs_unchanged
report = {
    'protocol': 'archcanvas-au3-current-docs-semantic-final-audit/1',
    'startedAt': started,
    'finishedAt': datetime.datetime.now(datetime.timezone.utc).isoformat(),
    'auditor': 'AI subagent /root/au3_pixel_audit',
    'status': 'passed-with-stated-scope' if passed else 'failed-with-findings',
    'scope': 'Current au3 documentation semantic consistency and exact referenced byte readback. Current headers/tables and current matrix document reviewed; historical text retains its explicit version scope. No product, old evidence or current docs written. Exact current documents copied only into this attempt snapshots.',
    'testsRun': False, 'buildRun': False, 'validatorRun': False, 'modelsRun': False,
    'browserOperated': False, 'imagesViewedAgainThisAudit': False,
    'humanAcceptanceCertified': False, 'publicationCertified': False,
    'performanceCertified': False, 'currentCompleteReleaseBytesCertified': False,
    'initialFindingReceipt': initial,
    'repairReceipt': record(BASE + 'docs-release-scope-repair-attempt-1.json'),
    'ancestorReportTimeScopeReceipt': record(BASE + 'ancestor-report-time-scope-attempt-1.json'),
    'mutableStatusTransitionReceipts': [record(BASE + 'status-validation-link-attempt-1.json'), record(BASE + 'status-independent-input-link-attempt-1.json')],
    'auditorSource': source_record,
    'auditedDocuments': snapshots,
    'currentDocumentCount': len(snapshots),
    'semanticChecks': checks,
    'exactReadbackGroups': groups,
    'inputsBefore': before, 'inputsAfter': after, 'inputsUnchanged': inputs_unchanged,
    'remainingSemanticContradictionsFound': [] if passed else [c['check'] for c in checks if not c['passed']],
    'limits': [
        'Document consistency is not product quality, global aesthetics, physical publication, performance or human acceptance.',
        'Prior personal pixel audits are preserved, not repeated. The old MLP mismatch and separate Y648 retry remain distinct.',
        'Frozen release scope receipt is read; installed dependencies or full28523 report sourceManifest are not relabeled as current209 release input certification.',
        '4259 archive mapping/count/manifest is read and byte-bound; full archival content is not recursively reread by this semantic audit.',
        'No tests, build, models, browser, dependency install or validator run occurred in this audit.'
    ]
}
with (OUT / 'final-readback.json').open('x') as f:
    json.dump(report, f, ensure_ascii=False, indent=2)
    f.write('\n')
final = record(OUT / 'final-readback.json')
summary = ('# au3 当前文档语义末审\n\n'
           f"结果：`{report['status']}`。已核21份当前文档/状态，并冻结副本；两处独立发行范围问题已由主任务修复，原问题记录另存。当前表格第24行（completion）和第15行（handoff）明示两份Skill reference后改，不能称当前全发行字节认证。祖先报告新增冻结时点提示与最新矩阵链接，原段落逐字保留。\n\n"
           '36基线/3编辑/234工件、12小幅方向操作、36+19张AI像素审查、旧MLP失配与Y648独立补采、首例export-only和6项有限heightMm尾差均与状态一致。输入诊断保留6尝试/5完成、14eligible/10matched/4interactions、matched子集p95 3000ms；rAF不是呈现FPS。17模块与3起点、此前au3 4/3搭建链保留各自覆盖。\n\n'
           'M4仍partial、M5未开始；当前研究包未prepare/verify，分配/收集/真人均0。美观、真实尺寸、呈现性能和held取消仍未认证。本次只读文件/语义核对，不重跑测试/build/validator，不操作浏览器或执行模型。旧收据未修改。\n\n'
           f"`final-readback.json` SHA256 `{final['sha256']}`；逐项检查、原问题、修复收据、文档副本与前后摘要见JSON。\n")
with (OUT / 'README.md').open('x') as f:
    f.write(summary)
print(json.dumps({'status': report['status'], 'documents': len(snapshots), 'semanticChecks': len(checks),
                  'semanticFailures': report['remainingSemanticContradictionsFound'],
                  'bindingGroups': {k: {'count': v['count'], 'allMatch': v['allMatch']} for k, v in groups.items()},
                  'uniqueInputs': len(before), 'inputsUnchanged': inputs_unchanged,
                  'finalReceipt': final, 'currentStatus': record(status_path)}, ensure_ascii=False))
