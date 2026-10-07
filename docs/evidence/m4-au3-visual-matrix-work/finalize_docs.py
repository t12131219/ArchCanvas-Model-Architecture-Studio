"""Update current summaries after exact archival, without altering evidence originals."""
from pathlib import Path
import datetime, hashlib, json, subprocess

ROOT = Path(__file__).resolve().parents[3]
WORK = ROOT / 'docs/evidence/m4-au3-visual-matrix-work'
OUT = WORK / 'docs-finalize-attempt-1'

def bind(path):
    data = path.read_bytes()
    return {'path': str(path.relative_to(ROOT)) if path.is_relative_to(ROOT) else str(path),
            'bytes': len(data), 'sha256': hashlib.sha256(data).hexdigest()}

def replace_paragraph(path, index, replacement):
    paragraphs = path.read_text().split('\n\n')
    paragraphs[index] = replacement
    path.write_text('\n\n'.join(paragraphs))

def replace_row(path, key, replacement):
    lines = path.read_text().splitlines()
    hits = [i for i, line in enumerate(lines) if line.startswith('| ' + key + ' |')]
    if len(hits) != 1:
        raise ValueError(f'{path}: ambiguous current row {key}: {hits}')
    lines[hits[0]] = replacement
    path.write_text('\n'.join(lines) + '\n')

def main():
    archive = ROOT / 'docs/evidence/before-m4-au3-full-matrix/manifest.json'
    manifest = json.loads(archive.read_text())
    # The archive is independently checked by its runner; also require its explicit success.
    assert manifest.get('sourceBeforeAfterExact') is True
    OUT.mkdir(exist_ok=False)
    main_files = ['README.md', 'docs/acceptance.md', 'docs/browser-visual-matrix-protocol.md',
                  'docs/capability-matrix.md', 'docs/evidence/README.md', 'docs/m4-completion.md',
                  'docs/m4-human-review-handoff.md']
    historical = ['docs/m4-ai-usability-audit.md', 'docs/m4-authoring-feedback.md',
                  'docs/m4-authoring.md', 'docs/m4-bcf-browser-matrix.md', 'docs/m4-exit-audit.md',
                  'docs/m4-performance.md', 'docs/m4-routing-refinement.md', 'docs/m4-research-protocol.md']
    skill_files = ['skills/archcanvas/references/formal-alpha.md',
                   'skills/archcanvas/references/runtime-compatibility.md']
    targets = [ROOT / name for name in main_files + historical + skill_files]
    targets.append(ROOT / 'docs/evidence/m4-human-review-handoff-status.json')
    before = [bind(path) for path in targets]
    archive_binding = bind(archive)
    for name in main_files:
        path = ROOT / name
        prefix = 'docs/' if name == 'README.md' else '../' if name == 'docs/evidence/README.md' else ''
        evidence = '' if name == 'docs/evidence/README.md' else 'docs/evidence/' if name == 'README.md' else 'evidence/'
        summary = (
            '当前（2026-10-06）构建仍为 `index-au3IB_0Q.js` / `index-B6WbMowt.css`。'
            f'本轮[au3 浏览器矩阵与四向操作]({prefix}m4-au3-current-matrix.md)已 collect 36 基线＋3 编辑后视图、234 工件；'
            '三个模型共12方向的实际拖动、撤销重做、保存重开有独立核对。'
            '36张fit及19张局部/编辑图分别AI审查，旧MLP右移失配保留，新起点补采单列。'
            'CNN外绕残差、窄缝拥挤、MLP边界折角和Transformer小移大改线仍是具体问题；文件完整不认证美观或出版。'
            '当前full observer保留6尝试/5完成、14eligible/10matched/4interactions、matched子集p95 3000ms；'
            '约1秒rAF间隔不是呈现帧认证。产品源码/build未改，沿用源码精确绑定的179/179、strict/build exit0；'
            '此前发行9/9是其209源码/654依赖/5symlink冻结副本范围，后续Skill文档改动不称同一完整发行字节。'
            '已有au3 4节点3边搭建链保存重开、静态生成及新工作副本保存保持独立证据；17模块＋3起点不等于逐模块完整验收。'
            'M4 partial、M5未开始，当前研究包未prepare/verify、0分配/收集/真人；AI不能替代真人。'
            f'[文档更新前归档]({evidence}before-m4-au3-full-matrix/manifest.json)保存此前4233绑定、24末读supplemental及两个原receipt；'
            '下方旧“当前/本轮/最终”只指各自版本和冻结时点。'
        )
        replace_paragraph(path, 1, summary)
    for name in historical:
        replace_paragraph(ROOT / name, 1,
            '当前正式构建仍为 `index-au3IB_0Q.js` / `index-B6WbMowt.css`，最新范围见'
            '[au3矩阵、四向操作与输入诊断](m4-au3-current-matrix.md)。39例文件已collect，'
            '三模型四向/history/save-reopen已独审；像素问题与性能未通过项保留，AI真人0、M4 partial、M5未开始。'
            '下方记录保留各自历史构建/时点，不继承为最新浏览器或研究认证。当前au3研究包仍未prepare/verify，'
            '旧研究席位不可分配。此前seal与末读原字节见'
            '[更新前归档](evidence/before-m4-au3-full-matrix/manifest.json)。')
    completion = ROOT / 'docs/m4-completion.md'
    replace_row(completion, 'M4-05 真浏览器性能', '| M4-05 真浏览器性能 | 当前full observer诊断；呈现门未认证 | 6尝试/5完成，14eligible/10matched/4interactions，matched子集p95 3000ms；约1秒rAF间隔。数据保留完整分母，不认证总体INP或呈现FPS，fixed font/hardware/held cancel仍缺证。 |')
    replace_row(completion, 'M4-06 空间连续性与出版', '| M4-06 空间连续性与出版 | 当前39工件完整；三模型四向/history/save-reopen有界通过 | 36基线＋3编辑后已collect；AI像素范围和失配另列。CNN外绕、边界拥挤、MLP折角、Transformer改线仍是问题；真实尺寸出版与全图美观未认证。 |')
    capability = ROOT / 'docs/capability-matrix.md'
    # The file also contains historical rows with the same label; edit only the first current table.
    replacements = {
        '层级展开': '| 层级展开 | Alpha有界；179/179与当前矩阵 | 九真实authored frontiers×四规格已采36基线；不造MLP/CNN深层级。canonical对象/端口/sourceIR与实际SVG保持，真实尺寸人审未认证。 |',
        '画布缩放与实际手势': '| 画布缩放与实际手势 | 三模型小幅叶对象四向/history通过 | 12方向实际native drag、undo/redo及保存重开；非所有对象/位移/pins覆盖。held-pointer cancel/presented FPS/font/hardware仍开放。 |',
        '保存与冲突': '| 保存与冲突 | CAS有界；当前三模型移动保存重开独审 | storage/visual revision分离；三模型SVG/几何和envelope一致，reopen清history/fit相机。au3 authored4/3链另证；imported alias刷新未复验。 |',
        'SVG': '| SVG | 当前36基线＋3编辑后工件通过 | 39case×6文件与actual UUID/源IR/Canvas/Scene精确绑定；首例export-only、6height末位容差披露。PDF/PNG/物理阅读守各自范围，artifactCoverage不认证美观。 |',
        'Publication quality / performance': '| Publication quality / performance | M4 partial；0真人 | 当前39工件已collect，AI局部/fit审查发现路径及拥挤问题。新full observer仅工程诊断，物理印样/presented/fonts/hardware/activecancel未认证；研究包未准备。 |',
    }
    lines = capability.read_text().splitlines()
    for key, replacement in replacements.items():
        index = next(i for i, line in enumerate(lines) if line.startswith('| ' + key + ' |'))
        lines[index] = replacement
    capability.write_text('\n'.join(lines) + '\n')
    handoff = ROOT / 'docs/m4-human-review-handoff.md'
    lines = handoff.read_text().splitlines()
    for key, replacement in {
        '当前完整浏览器矩阵': '| 当前完整浏览器矩阵 | au3已collect39例/234工件 | 36baseline＋3edited；AI像素审查单列，首例export-only和6height末位差披露，真人仍pending。 |',
        '当前au3代表浏览器': '| 当前au3代表浏览器 | 当前矩阵＋三模型12方向/history/save-reopen | 小幅叶对象操作有界通过；旧MLP右移pixel失配和独立补采保留。au3 authored4/3链独证，imported alias刷新/真人/物理出版未认证。 |',
    }.items():
        index = next(i for i, line in enumerate(lines) if line.startswith('| ' + key + ' |'))
        lines[index] = replacement
    handoff.write_text('\n'.join(lines) + '\n')
    english = (
        "The configured formal checkout's au3IB_0Q/B6WbMowt assets now have a separately collected 36-baseline plus three-edited browser matrix in docs/m4-au3-current-matrix.md. "
        "Nine real authored frontiers use color/monochrome and 85/180 mm; 39 cases/234 files are artifact-complete, with human review pending. "
        "Three models each have bounded native four-direction leaf movement, undo/redo, save and reopen evidence. "
        "AI fit/local image review retains a stale MLP right-move screenshot and a separate retry, CNN residual detours/close ports, MLP boundary alignment and Transformer rerouting instability. "
        "File consistency is not global aesthetics or physical publication approval. Current full observer records six attempts including one no-input, five completed operations, 14 eligible/10 matched inputs and four interactions with matched-subset p95 3000 ms; rAF cadence is not presented FPS. "
        "The product/source/build remain unchanged from the 179/179 and strict/build receipts; the earlier standalone9/9 belongs to its frozen release copy, whose two Skill references were later edited. "
        "The independently reviewed au3 four-node/three-edge authored workflow remains bounded evidence; the 17-module catalog and three transparent starting graphs are not per-module generation or human certification. "
        "No current research package has been prepared or verified; zero researchers, M4 partial, M5 not started. Resolve actual runtime assets and origins before claiming support; resolved fonts/hardware, presented performance, held cancellation and publication remain open."
    )
    for name in skill_files:
        replace_paragraph(ROOT / name, 2, english)
    status_path = ROOT / 'docs/evidence/m4-human-review-handoff-status.json'
    status = json.loads(status_path.read_text())
    status['schemaVersion'] = 10
    status['generatedAt'] = datetime.datetime.now(datetime.timezone.utc).isoformat()
    status['scope'] = 'Unchanged au3 product; current 36 baseline + 3 edited artifact matrix, bounded three-model native four-direction/history/persistence and AI pixel review, plus six-attempt full-observer diagnostic. M4 partial; no human, physical publication, presented performance or M5 certification.'
    status['tests']['rerunThisCollectionRound'] = False
    status['tests']['standalone']['currentFullReleaseFilesStillExact'] = False
    status['tests']['standalone']['laterSkillReferenceEdits'] = True
    status['tests']['standalone']['scope'] += ' Later Skill reference edits are not the same complete release bytes; product implementation/assets remain exact.'
    status['previousBoundedBrowser'] = status.pop('currentBrowser')
    status['currentBrowser'] = {
        'build': status['productionBuild'], 'artifactCoverage': 'complete',
        'baselineCases': 36, 'authoredFrontiers': 9, 'editedCases': 3, 'captureFiles': 234,
        'manifest': 'docs/evidence/browser-visual-matrix-au3-current/manifest.json',
        'independentReceipt': 'docs/evidence/m4-au3-visual-matrix-work/independent-audit/final-readback-attempt-2/receipt.json',
        'fitPixelReview': 'docs/evidence/m4-au3-visual-matrix-work/pixel-audit/all-36-fit.receipt.json',
        'localEditedPixelReview': 'docs/evidence/m4-au3-visual-matrix-work/pixel-audit/gestures/three-model-local-and-edited.receipt.json',
        'fourDirectionOperations': 12, 'models': ['transformer', 'mlp', 'residual_cnn'],
        'scope': '24 CSS-pixel moves of one leaf per model; grid-rounded 28/32 world units, undo/redo and save/reopen. No arbitrary object/delta, existing pins, ancestor move or active cancellation coverage.',
        'firstCaseExportOnly': 'transformer-level0-paper-180', 'storedSnapshotCases': 38,
        'heightMmOnlyToleranceCases': 6, 'heightMmTolerance': 1e-10,
        'fitImagesReviewed': 36, 'localAndEditedImagesReviewed': 19, 'localAndEditedMatched': 18,
        'retainedPixelMismatch': 'MLP original right image rev22/X138 versus DOMrev23/X142; retry from savedY648/rev36 is separate',
        'pixelScopeIsAiOnly': True, 'publicationCertified': False, 'globalRouteBeautyCertified': False,
        'humanAcceptanceCertified': False, 'freshImportedCanvasAliasSaveReopenCertified': False,
        'environment': 'Current public DOM viewport/camera/assets; matrix UA/DPR explicitly historical same-IAB provenance. Later harness observes current UA/DPR without rewriting matrix receipts.',
        'retainedVisualIssues': ['CNN collapsed residual detour beyond outer frame', 'MLP boundary short stair routes', 'CNN left outside parent and vertical close ports', 'Transformer small left move causes large elbow displacement'],
        'service': {'url': 'http://127.0.0.1:43355/', 'toolSessionId': 9981, 'user8765Touched': False, 'availabilityAfterHostTerminationPromised': False},
    }
    result = json.loads((WORK / 'input-diagnostic/validation-attempt-1/stdout.json').read_text())
    status['currentInputDiagnostic'] = {
        'raw': 'docs/evidence/m4-au3-visual-matrix-work/input-diagnostic/full-observer-raw-chunked.json',
        'validationReceipt': 'docs/evidence/m4-au3-visual-matrix-work/input-diagnostic/validation-attempt-1/command-receipt.json',
        'protocol': 'archcanvas-input-observation/2', 'attempts': 6, 'completedOperations': 5,
        'noInputAttempts': 1, 'renderedExpandedObjects': 304, 'allObjectsSimultaneouslyInViewportCertified': False,
        'completeBuffers': result['completeBuffers'], 'dropped': result['dropped'], 'errors': result['errors'],
        'eligibleDiscreteInputs': result['latency']['eligibleDiscreteInputs'], 'matchedDiscreteInputs': result['latency']['matchedDiscreteInputs'],
        'matchedInteractions': result['latency']['matchedInteractions'], 'matchedSubsetP95Ms': result['latency']['matchedInteractionP95Ms'],
        'rafCadenceFps': result['frameCadence']['fps'], 'idleRafCadenceFps': result['idleCadence']['fps'],
        'presentedPerformanceCertified': False, 'overallInpCertified': False, 'activeCancellationCertified': False,
        'currentUaDprObserved': True, 'resolvedFontsHardwareCertified': False,
        'betaTargetProvenance': 'Technical plan §18.5 initial Beta p95≤50ms/FPS≥50; not a newly imposed M4 numeric hard gate',
        'service': {'url': 'http://127.0.0.1:33057/__m4/', 'toolSessionId': 23644},
    }
    status['openGates'] = ['3–5 actual researchers original five-step tasks; current package not prepared/verified',
                          'physical 85/180mm visual publication and deep glyph review',
                          'global route aesthetics and stability including recorded candidates',
                          'fixed hardware/resolved fonts and actual continuous browser presentation performance',
                          'held-pointer active gesture cancellation',
                          'expanded authored catalog; current17base modules plus3transparent starts']
    status['historicalArchive'] = {'manifest': archive_binding['path'], 'manifestSha256': archive_binding['sha256'],
        'files': 4259, 'scope': '4233 previous seal bindings +24 supplemental +seal +final receipt; immutable historical bytes'}
    new_refs = [ROOT / 'docs/evidence/browser-visual-matrix-au3-current/manifest.json',
        WORK / 'collection-attempt-1/attempt-receipt.json',
        WORK / 'independent-audit/final-readback-attempt-2/receipt.json',
        WORK / 'pixel-audit/all-36-fit.receipt.json',
        WORK / 'pixel-audit/gestures/three-model-local-and-edited.receipt.json',
        WORK / 'input-diagnostic/validation-attempt-1/command-receipt.json', archive]
    status['evidenceRefs'] += [bind(path) for path in new_refs]
    status_path.write_text(json.dumps(status, indent=2, ensure_ascii=False) + '\n')
    (OUT / 'mutation-receipt.json').write_text(json.dumps({'schemaVersion': 1, 'before': before,
        'after': [bind(path) for path in targets], 'archive': archive_binding,
        'scope': 'Current documentation/status only; no old evidence, product or build changed'}, indent=2) + '\n')
    validator = Path('/home/fzg/.codex/skills/.system/skill-creator/scripts/quick_validate.py')
    argv = ['/home/fzg/anaconda3/bin/python', str(validator), 'skills/archcanvas']
    skill_before = [bind(path) for path in sorted((ROOT/'skills/archcanvas').rglob('*')) if path.is_file()]
    command = subprocess.run(argv, cwd=ROOT, capture_output=True)
    (OUT/'skill.stdout.log').write_bytes(command.stdout)
    (OUT/'skill.stderr.log').write_bytes(command.stderr)
    (OUT/'skill-validation.json').write_text(json.dumps({'argv': argv, 'exitCode': command.returncode,
        'validator': bind(validator), 'skillFilesBefore': skill_before,
        'skillFilesAfter': [bind(path) for path in sorted((ROOT/'skills/archcanvas').rglob('*')) if path.is_file()],
        'scope': 'Host Markdown/YAML validation only; no model/runtime or dependency install'}, indent=2)+'\n')
    print(json.dumps({'changedFiles': len(targets), 'skillValidationExitCode': command.returncode,
                      'archive': archive_binding}, ensure_ascii=False))

if __name__ == '__main__':
    main()
