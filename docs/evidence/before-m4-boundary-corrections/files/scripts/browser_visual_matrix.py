#!/usr/bin/env python3
"""Prepare and bind a real-browser visual gold matrix without granting human acceptance.

Studio screenshots must be captured by an operator in the actual browser. This
script checks local artifact consistency and produces a review index; it cannot
establish participant identity, image content or aesthetic acceptance.
"""
from __future__ import annotations

import argparse
import hashlib
import html
import json
import math
import re
import shutil
import subprocess
import sys
import tempfile
from datetime import datetime, timezone
from pathlib import Path
import xml.etree.ElementTree as ET

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / 'src'))
from archcanvas_publication import export_svg

PROTOCOL = 'archcanvas-browser-visual-matrix/1'
CAPTURE_PROTOCOL = 'archcanvas-browser-visual-capture/1'
FIXTURES = ('transformer', 'mlp', 'residual_cnn')
FIELDS = ('displayAliases', 'nodeStyleOverrides', 'edgeStyleOverrides', 'legendItems', 'annotations', 'layout', 'pinnedObjects', 'title', 'pageSpec')
CRITERIA = ('layout', 'hierarchyReading', 'whitespace', 'colorAndMonochromeMeaning', 'fontAndPhysicalReadability', 'routingAndConnections')


def now() -> str:
    return datetime.now(timezone.utc).isoformat()


def sha(raw: bytes) -> str:
    return hashlib.sha256(raw).hexdigest()


def canonical(value: object) -> str:
    return sha(json.dumps(value, sort_keys=True, ensure_ascii=False, allow_nan=False, separators=(',', ':')).encode())


def obj(value: object, label: str) -> dict:
    if not isinstance(value, dict):
        raise ValueError(f'{label} must be an object.')
    return value


def read(path: Path) -> dict:
    return obj(json.loads(path.read_bytes()), path.name)


def write(path: Path, value: object) -> None:
    path.write_text(json.dumps(value, ensure_ascii=False, allow_nan=False, indent=2) + '\n', encoding='utf-8')


def binding(path: Path, parent: Path) -> dict:
    raw = path.read_bytes()
    return {'path': str(path.relative_to(parent)), 'sha256': sha(raw), 'bytes': len(raw)}


def managed(path: Path, parent: Path) -> Path:
    if not path.resolve().is_relative_to(parent.resolve()):
        raise ValueError('Matrix evidence path escapes its declared directory.')
    current = path
    while current != parent:
        if current.is_symlink():
            raise ValueError('Matrix evidence must use regular files, not symlinks.')
        current = current.parent
    if not path.is_file():
        raise ValueError(f'Missing actual evidence file: {path}')
    return path


def xml_value(raw: bytes) -> object:
    if len(raw) > 8_000_000 or re.search(rb'<!\s*(?:DOCTYPE|ENTITY)|<\?', raw, re.I):
        raise ValueError('Browser Scene XML has unsafe declarations or exceeds budget.')
    root = ET.fromstring(raw)
    if root.tag != '{http://www.w3.org/2000/svg}svg':
        raise ValueError('Browser Scene must be actual SVG XML.')
    def element(node):
        return [node.tag, sorted(node.attrib.items()), node.text or '', node.tail or '', [element(child) for child in node]]
    return element(root)


def semantic_svg_digest(raw: bytes) -> str:
    return canonical(xml_value(raw))


def prepare(core_dir: Path, output: Path) -> dict:
    core_dir, output = core_dir.resolve(), output.absolute()
    if output.exists():
        raise ValueError('Matrix already exists; prepare a fresh path to preserve prior evidence.')
    report = read(core_dir / 'visual-gold-report.json')
    if report.get('auditCompleted') is not True:
        raise ValueError('A completed actual-source core candidate report is required.')
    variants = report.get('variants')
    if not isinstance(variants, list):
        raise ValueError('Core variants must be a list.')
    expected, frontiers = [], []
    core_files = []
    for fixture in FIXTURES:
        architecture = read(core_dir / f'{fixture}.architecture.json')
        by_id = {node['id']: node for node in architecture['nodes']}
        def depth(node):
            result = 0
            while node.get('parentId'):
                result += 1
                node = by_id[node['parentId']]
            return result
        maximum = max(depth(node) for node in by_id.values() if node['children'])
        # Level zero is the opened model root. Only authored non-atomic
        # containers can add frontier levels; shallow models do not grow to 3.
        for level in range(min(3, maximum) + 1):
            ids = [node['id'] for node in architecture['nodes'] if node['children'] and depth(node) <= level]
            frontiers.append({'fixture': fixture, 'level': level,
                'name': 'overview' if level == 0 else f'authored-depth-{level}',
                'expandedIds': ids, 'expandedLabels': [by_id[identity]['label'] for identity in ids],
                'maxAuthoredContainerDepth': maximum})
            for preset in ('paper', 'monochrome'):
                for width in (85, 180):
                    name = f'{fixture}-level{level}-{preset}-{width}'
                    matches = [variant for variant in variants if variant.get('name') == name]
                    if len(matches) != 1:
                        raise ValueError(f'Missing or duplicate exact core variant: {name}')
                    variant = matches[0]
                    document_path = managed(core_dir / f'{name}.canvas.json', core_dir)
                    document = read(document_path)
                    if (document['architecture'] != architecture or sorted(document['expandedIds']) != sorted(ids)
                            or document['pageSpec']['preset'] != preset or document['pageSpec']['widthMm'] != width):
                        raise ValueError(f'Core frontier/page/source differs from its authored requirement: {name}')
                    paths = [document_path, managed(core_dir / f'{name}.svg', core_dir)]
                    core_files.extend(binding(path, core_dir) for path in paths)
                    expected.append({'variantId': name, 'fixture': fixture, 'level': level, 'preset': preset, 'widthMm': width,
                        'documentId': document['id'], 'sourceDigest': architecture['sourceDigest'], 'irDigest': architecture['irDigest'],
                        'expandedIds': ids, 'baselineCanvasCanonicalDigest': canonical(document),
                        'canvasFile': str(document_path), 'svgFile': str(core_dir / f'{name}.svg'),
                        'visibleNodes': variant['visibleNodes'], 'physicalPreflight': variant['physicalPreflight']})
    if len(variants) != len(expected) or len(expected) != 36 or len(frontiers) != 9:
        raise ValueError('The actual three fixtures must have precisely 9 authored frontiers / 36 declared variants.')
    assets = [path for path in (ROOT / 'studio/dist').rglob('*') if path.is_file()]
    if not (ROOT / 'studio/dist/index.html').is_file():
        raise ValueError('Build the real Studio before freezing a browser matrix.')
    implementation = [*sorted((ROOT / 'studio/src/core').glob('*.ts')),
        *sorted((ROOT / 'src/archcanvas_python').glob('*.py')),
        *sorted((ROOT / 'src/archcanvas_publication').glob('*.py')),
        ROOT / 'scripts/browser_visual_matrix.py', ROOT / 'scripts/browser_visual_core.mjs']
    spec = {'schemaVersion': 1, 'protocol': PROTOCOL, 'preparedAt': now(), 'coreDirectory': str(core_dir),
        'visualAcceptance': 'pending-human-and-browser-review', 'expectedBaselineCount': 36,
        'frontiers': frontiers, 'variants': expected, 'coreFiles': core_files,
        'coreReportDigest': sha((core_dir / 'visual-gold-report.json').read_bytes()),
        'implementationFiles': [binding(path, ROOT) for path in implementation],
        'buildFiles': [binding(path, ROOT / 'studio/dist') for path in sorted(assets)],
        'editedAfterRequirement': {'goldenModels': list(FIXTURES), 'minimum': 'one separately bound edited-after case per model',
            'scope': 'No claim that baseline captures establish editing or all 36 combinations were edited.'},
        'limitations': ['Core candidate SVGs are not browser screenshots.',
            'A matrix collection checks local file/Scene consistency, not image content or aesthetic acceptance.',
            'Browser viewport captures are displayed at recorded zoom; SVG widthMm is the publication physical size.']}
    output.parent.mkdir(parents=True, exist_ok=True)
    temporary = Path(tempfile.mkdtemp(prefix='.browser-matrix-prepare-', dir=output.parent))
    try:
        write(temporary / 'spec.json', spec)
        write(temporary / 'capture-template.json', {'schemaVersion': 1, 'protocol': PROTOCOL, 'captures': []})
        lines = ['# Actual browser capture tasks', '', '36 baseline captures + separate edited-after cases for each golden model.',
            'These tasks are unexecuted; no browser screenshot or human acceptance is implied.', '',
            '| Variant | Open containers (complete frontier) | Nodes | Page |', '|---|---|---:|---|']
        for variant in expected:
            frontier = next(item for item in frontiers if item['fixture'] == variant['fixture'] and item['level'] == variant['level'])
            lines.append(f"| {variant['variantId']} | {', '.join(frontier['expandedLabels'])} | {variant['visibleNodes']} | {variant['widthMm']} mm / {variant['preset']} |")
        (temporary / 'capture-tasks.md').write_text('\n'.join(lines) + '\n', encoding='utf-8')
        write(temporary / 'screen-receipt-template.json', {'schemaVersion': 1, 'protocol': CAPTURE_PROTOCOL,
            'caseId': None, 'variantId': None, 'state': 'baseline', 'captureKind': 'studio-browser', 'capturedAt': None,
            'documentBinding': {'documentId': None, 'revision': None, 'sourceDigest': None, 'irDigest': None},
            'pageSpec': {'widthMm': None, 'preset': None}, 'expandedIds': [],
            'screenshotDigest': None, 'browserSceneDigest': None,
            'environment': {'userAgent': None, 'browserVersion': None, 'viewport': {'width': None, 'height': None},
                'devicePixelRatio': None, 'hardware': None, 'fontEvidence': []},
            'camera': {'transform': None, 'sceneScreenBounds': None},
            'loadedBuildAssets': [], 'captureScope': 'studio-viewport',
            'limitations': ['Operator-collected receipt; hashes cannot prove screenshot content or native provenance.']})
        temporary.rename(output)
        return spec
    except Exception:
        shutil.rmtree(temporary)
        raise


def verified_spec(directory: Path) -> dict:
    spec = read(directory / 'spec.json')
    if spec.get('schemaVersion') != 1 or spec.get('protocol') != PROTOCOL:
        raise ValueError('Unsupported browser matrix specification.')
    for field, root in (('implementationFiles', ROOT), ('buildFiles', ROOT / 'studio/dist'), ('coreFiles', Path(spec['coreDirectory']))):
        for entry in spec[field]:
            if binding(managed(root / entry['path'], root), root) != entry:
                raise ValueError(f'Frozen {field} changed; use a fresh matrix specification.')
    if sha((Path(spec['coreDirectory']) / 'visual-gold-report.json').read_bytes()) != spec['coreReportDigest']:
        raise ValueError('Frozen core candidate report changed.')
    return spec


def collect(matrix: Path, captures_path: Path, output: Path) -> dict:
    matrix, captures_path, output = matrix.resolve(), captures_path.resolve(), output.absolute()
    spec = verified_spec(matrix)
    records = read(captures_path)
    if records.get('schemaVersion') != 1 or records.get('protocol') != PROTOCOL or not isinstance(records.get('captures'), list):
        raise ValueError('Unsupported matrix captures list.')
    if output.exists():
        raise ValueError('Collection output already exists; preserve the existing snapshot.')
    variants = {item['variantId']: item for item in spec['variants']}
    captured, identities, baselines = [], set(), set()
    for record in records['captures']:
        record = obj(record, 'capture')
        case = record.get('caseId')
        variant = variants.get(record.get('variantId'))
        state = record.get('state')
        if not isinstance(case, str) or not re.fullmatch(r'[A-Za-z0-9_-]{1,100}', case) or case in identities or variant is None or state not in ('baseline', 'edited'):
            raise ValueError('Capture needs a unique safe caseId and an actual declared variant/state.')
        identities.add(case)
        if state == 'baseline':
            if variant['variantId'] in baselines:
                raise ValueError('Duplicate baseline capture for a matrix variant.')
            baselines.add(variant['variantId'])
        files = {name: managed(captures_path.parent / record[name], captures_path.parent).read_bytes()
                 for name in ('canvas', 'svg', 'exportReceipt', 'screenshot', 'browserScene', 'screenReceipt')}
        payload = obj(json.loads(files['canvas']), 'capture Canvas')
        document = obj(payload.get('document', payload), 'capture CanvasDocument')
        baseline = read(Path(variant['canvasFile']))
        if (document.get('architecture') != baseline['architecture'] or document.get('id') != variant['documentId']
                or document.get('sourceBindingDigest') != variant['sourceDigest']
                or sorted(document.get('expandedIds', [])) != sorted(variant['expandedIds'])
                or document.get('pageSpec', {}).get('widthMm') != variant['widthMm']
                or document.get('pageSpec', {}).get('preset') != variant['preset']):
            raise ValueError(f'Actual Canvas differs from the declared source/frontier/page: {case}')
        if type(document.get('revision')) is not int or document['revision'] < 0:
            raise ValueError('Capture visual revision must be a nonnegative integer.')
        changed = [field for field in FIELDS if document.get(field) != baseline.get(field)]
        if state == 'baseline' and any(field in changed for field in FIELDS if field != 'layout'):
            raise ValueError('Edited visual fields cannot be labelled as an unedited baseline.')
        if state == 'edited' and not changed:
            raise ValueError('Edited-after capture requires actual changed visual fields.')
        receipt = obj(json.loads(files['exportReceipt']), 'export receipt')
        if (receipt.get('format') != 'svg' or receipt.get('documentId') != document['id'] or receipt.get('revision') != document['revision']
                or receipt.get('sourceDigest') != variant['sourceDigest'] or receipt.get('irDigest') != variant['irDigest']
                or receipt.get('outputDigest') != sha(files['svg']) or receipt.get('bytes') != len(files['svg'])
                or receipt.get('widthMm') != variant['widthMm'] or receipt.get('exportScope') != {'kind': 'document'}):
            raise ValueError('Actual publication SVG receipt does not bind the current complete Canvas.')
        shot = files['screenshot']
        if not (shot.startswith(b'\xff\xd8\xff') or shot.startswith(b'\x89PNG\r\n\x1a\n') or (shot[:4] == b'RIFF' and shot[8:12] == b'WEBP')):
            raise ValueError('Actual Studio screenshot must be JPEG, PNG or WebP.')
        screen = obj(json.loads(files['screenReceipt']), 'screen receipt')
        document_binding = {'documentId': document['id'], 'revision': document['revision'], 'sourceDigest': variant['sourceDigest'], 'irDigest': variant['irDigest']}
        if (screen.get('schemaVersion') != 1 or screen.get('protocol') != CAPTURE_PROTOCOL or screen.get('caseId') != case
                or screen.get('variantId') != variant['variantId'] or screen.get('state') != state
                or screen.get('captureKind') != 'studio-browser' or screen.get('documentBinding') != document_binding
                or screen.get('pageSpec') != {'widthMm': variant['widthMm'], 'preset': variant['preset']}
                or sorted(screen.get('expandedIds', [])) != sorted(variant['expandedIds'])
                or screen.get('screenshotDigest') != sha(shot) or screen.get('browserSceneDigest') != semantic_svg_digest(files['browserScene'])):
            raise ValueError('Screen receipt differs from actual screenshot/DOM/source/frontier/page binding.')
        if not isinstance(screen.get('capturedAt'), str):
            raise ValueError('Capture timestamp must be ISO text with a timezone.')
        time = datetime.fromisoformat(screen['capturedAt'].replace('Z', '+00:00'))
        if time.tzinfo is None or time.utcoffset() is None:
            raise ValueError('Capture timestamp must include a timezone.')
        environment = obj(screen.get('environment'), 'screen environment')
        viewport = obj(environment.get('viewport'), 'viewport')
        for value in (*[viewport.get(field) for field in ('width', 'height')], environment.get('devicePixelRatio')):
            try:
                valid = type(value) in (int, float) and value > 0 and math.isfinite(value)
            except OverflowError:
                valid = False
            if not valid:
                raise ValueError('Viewport/DPR must be positive finite observed values.')
        if not isinstance(environment.get('userAgent'), str) or not environment['userAgent']:
            raise ValueError('Capture requires the actual browser userAgent.')
        camera = obj(screen.get('camera'), 'camera')
        if not isinstance(camera.get('transform'), str) or not camera['transform'] or not isinstance(camera.get('sceneScreenBounds'), dict):
            raise ValueError('Capture requires observed camera transform and Scene screen bounds.')
        bounds = camera['sceneScreenBounds']
        for field in ('x', 'y', 'width', 'height'):
            value = bounds.get(field)
            try:
                valid = type(value) in (int, float) and math.isfinite(value) and (field in ('x', 'y') or value > 0)
            except OverflowError:
                valid = False
            if not valid:
                raise ValueError('Scene screen bounds must be finite observed coordinates with positive size.')
        loaded = screen.get('loadedBuildAssets')
        expected_assets = {entry['path']: entry['sha256'] for entry in spec['buildFiles'] if entry['path'].endswith(('.js', '.css'))}
        if not isinstance(loaded, list) or not loaded:
            raise ValueError('Capture requires observed loaded JS/CSS assets bound to the frozen build.')
        actual_assets = {}
        for item in loaded:
            item = obj(item, 'loaded asset')
            path = item.get('path')
            if path in actual_assets or expected_assets.get(path) != item.get('sha256') or not isinstance(item.get('url'), str) or not item['url'].endswith('/' + path):
                raise ValueError('Loaded asset does not match the frozen JS/CSS build.')
            actual_assets[path] = item['sha256']
        if actual_assets != expected_assets:
            raise ValueError('Capture omits a frozen JS/CSS build asset.')
        captured.append({'record': record, 'variant': variant, 'document': document, 'receipt': receipt,
                         'screen': screen, 'changedVisualFields': changed, 'files': files})
    output.parent.mkdir(parents=True, exist_ok=True)
    temporary = Path(tempfile.mkdtemp(prefix='.browser-matrix-collect-', dir=output.parent))
    try:
        input_path = temporary / 'core-input.json'
        write(input_path, [{'document': item['document']} for item in captured])
        node = shutil.which('node')
        result = subprocess.run([node, str(ROOT / 'scripts/browser_visual_core.mjs'), str(input_path), str(temporary / 'expected')],
                                cwd=ROOT, capture_output=True, text=True, timeout=60)
        if result.returncode:
            raise ValueError('Independent formal core check failed: ' + result.stderr[-2000:])
        input_path.unlink()
        checked = []
        for index, item in enumerate(captured):
            files, receipt, record = item['files'], item['receipt'], item['record']
            expected_dom = (temporary / 'expected' / f'{index}.interactive.svg').read_bytes()
            expected_publication = (temporary / 'expected' / f'{index}.publication.svg').read_bytes()
            if semantic_svg_digest(expected_dom) != semantic_svg_digest(files['browserScene']):
                raise ValueError('Captured browser Scene differs from the actual Canvas in the formal interactive renderer.')
            if receipt.get('sceneSvgDigest') != sha(expected_publication) or receipt.get('inputSvgDigest') != sha(expected_publication):
                raise ValueError('Publication input digest differs from the exact captured Canvas.')
            normalized = export_svg(expected_publication.decode(), format='svg', width_mm=item['variant']['widthMm'], dpi=receipt['dpi'])['data']
            if normalized != files['svg'] or receipt.get('svgDigest') != sha(normalized):
                raise ValueError('Actual publication SVG differs from independent formal normalization.')
            directory = temporary / 'captures' / record['caseId']
            directory.mkdir(parents=True)
            suffix = '.jpg' if files['screenshot'].startswith(b'\xff\xd8') else '.png' if files['screenshot'].startswith(b'\x89PNG') else '.webp'
            names = {'canvas': 'canvas.json', 'svg': 'figure.svg', 'exportReceipt': 'export-receipt.json',
                     'screenshot': 'screenshot' + suffix, 'browserScene': 'browser-scene.svg', 'screenReceipt': 'screen-receipt.json'}
            for field, name in names.items():
                (directory / name).write_bytes(files[field])
            checked.append({'caseId': record['caseId'], 'variantId': record['variantId'], 'state': record['state'],
                'fixture': item['variant']['fixture'], 'fileConsistency': 'verified', 'visualReview': 'pending-human-review',
                'documentBinding': item['screen']['documentBinding'], 'pageSpec': item['screen']['pageSpec'],
                'expandedIds': item['document']['expandedIds'], 'changedVisualFields': item['changedVisualFields'],
                'canvasCanonicalDigest': canonical(item['document']), 'browserSceneDigest': semantic_svg_digest(expected_dom),
                'files': {field: binding(directory / name, temporary) for field, name in names.items()},
                'environment': item['screen']['environment'], 'camera': item['screen']['camera'],
                'physicalPreflight': receipt.get('physicalPreflight', item['variant']['physicalPreflight'])})
        # Expected previews help review missing cases; each is explicitly a core
        # candidate and cannot be counted as a captured browser image.
        previews = temporary / 'core-previews'
        previews.mkdir()
        for variant in spec['variants']:
            shutil.copyfile(variant['svgFile'], previews / (variant['variantId'] + '.svg'))
        edited_models = sorted({item['fixture'] for item in checked if item['state'] == 'edited'})
        missing = [item['variantId'] for item in spec['variants'] if item['variantId'] not in baselines]
        manifest = {'schemaVersion': 1, 'protocol': PROTOCOL, 'collectedAt': now(),
            'specDigest': sha((matrix / 'spec.json').read_bytes()), 'expectedBaselineCount': 36,
            'capturedBaselineCount': len(baselines), 'missingBaselineVariants': missing,
            'editedAfterModelsCaptured': edited_models, 'editedAfterModelsMissing': [fixture for fixture in FIXTURES if fixture not in edited_models],
            'artifactCoverage': 'complete' if not missing and len(edited_models) == 3 else 'incomplete',
            'visualAcceptance': 'pending-human-review', 'humanAcceptanceCertified': False,
            'captures': checked, 'variants': spec['variants'], 'buildFiles': spec['buildFiles'],
            'environmentConsistency': 'requires-independent-review',
            'limitations': ['Screenshot hashes do not prove content, capture time or genuine browser provenance.',
                'Screen receipts and loaded asset URLs are operator observations checked against frozen files.',
                'Viewport images at fit/zoom are not calibrated physical-size print samples; inspect 85/180 mm SVG separately.',
                'Geometry, exact DOM and publication bytes cannot establish aesthetics, font resolution or readable native pixels.',
                'Baseline images cannot establish edit/undo/save/reload tasks.']}
        write(temporary / 'manifest.json', manifest)
        write(temporary / 'review-template.json', {'protocol': PROTOCOL, 'reviewer': None, 'status': 'pending-human-review',
            'humanAcceptanceCertified': False, 'cases': [{'caseId': item['caseId'], 'status': 'pending',
                'criteria': {criterion: {'status': 'pending', 'notes': ''} for criterion in CRITERIA},
                'physicalSizeViewed': 'pending', 'browserPixelContentReviewed': 'pending'} for item in checked]})
        render_index(temporary / 'index.html', manifest)
        temporary.rename(output)
        return manifest
    except Exception:
        shutil.rmtree(temporary)
        raise


def render_index(path: Path, manifest: dict) -> None:
    escape = html.escape
    cards = []
    for variant in manifest['variants']:
        captures = [item for item in manifest['captures'] if item['variantId'] == variant['variantId'] and item['state'] == 'baseline']
        item = captures[0] if captures else None
        picture = item['files']['screenshot']['path'] if item else f"core-previews/{variant['variantId']}.svg"
        label = '真实 Studio 截图 · 待人工审看' if item else '缺浏览器截图 · 正式 core 候选预览'
        figure = item['files']['svg']['path'] if item else f"core-previews/{variant['variantId']}.svg"
        pt = variant['physicalPreflight']['minTextPt']
        links = f'<a href="{escape(figure)}">打开 {variant["widthMm"]} mm SVG</a>'
        if item:
            links += f'<a href="{escape(item["files"]["canvas"]["path"])}">Canvas</a><a href="{escape(item["files"]["screenReceipt"]["path"])}">采集收据</a>'
        cards.append(f'<article class="card" data-fixture="{escape(variant["fixture"])}"><header><b>{escape(variant["fixture"])} · L{variant["level"]}</b><span>{variant["widthMm"]} mm · {escape(variant["preset"])}</span></header><a class="preview" href="{escape(picture)}"><img loading="lazy" src="{escape(picture)}" alt="{escape(label)}"></a><p class="status {"captured" if item else "missing"}">{escape(label)}</p><p>{variant["visibleNodes"]} 个可见对象 · 最小文字 {pt:.2f} pt</p><nav>{links}</nav><small>{escape(variant["variantId"])}</small></article>')
    edits = []
    for item in manifest['captures']:
        if item['state'] != 'edited':
            continue
        files = item['files']
        edits.append(f'<article class="card"><header><b>{escape(item["caseId"])}</b><span>编辑后 · 待人工审看</span></header><a class="preview" href="{escape(files["screenshot"]["path"])}"><img src="{escape(files["screenshot"]["path"])}" alt="编辑后真实Studio截图"></a><p>{escape(", ".join(item["changedVisualFields"]))}</p><nav><a href="{escape(files["svg"]["path"])}">实际 SVG</a><a href="{escape(files["canvas"]["path"])}">Canvas</a></nav></article>')
    markup = '<!doctype html><html lang="zh-CN"><meta charset="utf-8"><meta name="viewport" content="width=device-width,initial-scale=1"><title>ArchCanvas 浏览器视觉黄金审看</title><style>body{margin:0;background:#eef2f4;color:#243441;font:15px/1.55 system-ui,sans-serif}main{max-width:1600px;margin:auto;padding:36px}h1{font-size:30px;margin:0 0 10px}.note{max-width:1050px;background:#fff8e8;padding:18px 22px;border-left:4px solid #bf9246;border-radius:5px}.stats{display:flex;gap:12px;margin:20px 0}.stats b{background:white;border:1px solid #d8e1e7;padding:12px 18px;border-radius:9px}.grid{display:grid;grid-template-columns:repeat(auto-fit,minmax(310px,1fr));gap:18px}.card{background:white;border:1px solid #d5e0e7;border-radius:12px;overflow:hidden;box-shadow:0 5px 18px #22344308}.card header{padding:15px 17px;display:flex;justify-content:space-between;border-bottom:1px solid #e8edf0}.card header span{font-size:12px;color:#5c7180}.preview{height:240px;display:flex;background:#fafbfc;justify-content:center;padding:12px}.preview img{max-width:100%;height:100%;object-fit:contain}.card p,.card nav,.card small{margin:10px 17px}.status{font-size:12px;font-weight:600}.missing{color:#956826}.captured{color:#226851}nav{display:flex;gap:14px;flex-wrap:wrap}a{color:#246b91;text-decoration:none}a:hover{text-decoration:underline}small{display:block;color:#778a97;font-size:11px;overflow-wrap:anywhere}.toolbar{margin:24px 0}button{background:white;color:#315164;border:1px solid #bccdd7;padding:8px 16px;border-radius:6px;margin-right:8px;cursor:pointer}h2{margin-top:34px;font-size:22px}</style><main><h1>ArchCanvas 浏览器视觉黄金审看</h1><p>三个源码模型 · 九个实际前沿 · 彩色/黑白 × 85/180 mm</p><div class="note"><b>人工验收尚未完成。</b>截图、DOM 与导出文件绑定只核证据一致性。缺图卡显示的是正式 core 候选，不能充作浏览器截图。请分别审看布局、层级、留白、色彩/黑白、字体与连线；屏幕 fit/zoom 预览不等于校准的真实尺寸印样。</div>'
    markup += f'<div class="stats"><b>浏览器基线 {manifest["capturedBaselineCount"]}/36</b><b>编辑后模型 {len(manifest["editedAfterModelsCaptured"])}/3</b><b>视觉门：待人工复核</b></div><p><a href="manifest.json">证据 manifest</a> · <a href="review-template.json">逐图人工评分模板</a></p><div class="toolbar"><button onclick="filterCards(\'all\')">全部</button><button onclick="filterCards(\'transformer\')">Transformer</button><button onclick="filterCards(\'mlp\')">MLP</button><button onclick="filterCards(\'residual_cnn\')">Residual CNN</button></div><section class="grid">' + ''.join(cards) + '</section><h2>编辑后导出单列证据</h2><p>没有编辑后截图和导出时不能由基础矩阵补齐此任务。</p><section class="grid">' + ''.join(edits) + '</section></main><script>function filterCards(value){document.querySelectorAll("[data-fixture]").forEach(card=>card.hidden=value!=="all"&&card.dataset.fixture!==value)}</script></html>'
    path.write_text(markup, encoding='utf-8')


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    commands = parser.add_subparsers(dest='command', required=True)
    preparation = commands.add_parser('prepare')
    preparation.add_argument('--core-dir', required=True, type=Path)
    preparation.add_argument('--output', required=True, type=Path)
    collection = commands.add_parser('collect')
    collection.add_argument('--matrix', required=True, type=Path)
    collection.add_argument('--captures', required=True, type=Path)
    collection.add_argument('--output', required=True, type=Path)
    verification = commands.add_parser('verify')
    verification.add_argument('--matrix', required=True, type=Path)
    stamping = commands.add_parser('stamp-hashes', help='Fill actual file hashes into an operator-observed screen receipt; does not create observations')
    stamping.add_argument('--receipt', type=Path, required=True)
    stamping.add_argument('--screenshot', type=Path, required=True)
    stamping.add_argument('--browser-scene', type=Path, required=True)
    args = parser.parse_args()
    try:
        if args.command == 'stamp-hashes':
            result = read(args.receipt)
            result['screenshotDigest'] = sha(args.screenshot.read_bytes())
            result['browserSceneDigest'] = semantic_svg_digest(args.browser_scene.read_bytes())
            write(args.receipt, result)
        else:
            result = prepare(args.core_dir, args.output) if args.command == 'prepare' else collect(args.matrix, args.captures, args.output) if args.command == 'collect' else {'protocol': PROTOCOL, 'frozenFilesUnchanged': bool(verified_spec(args.matrix.resolve())), 'visualAcceptance': 'not-evaluated'}
        print(json.dumps(result, ensure_ascii=False, indent=2))
    except (OSError, ValueError, TypeError, KeyError, ET.ParseError, subprocess.SubprocessError) as error:
        parser.exit(1, f'{error}\n')
    return 0


if __name__ == '__main__':
    raise SystemExit(main())
