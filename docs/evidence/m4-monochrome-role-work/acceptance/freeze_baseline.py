"""Freeze existing authority; never import the product to derive expectations."""
from __future__ import annotations

import hashlib
import json
from datetime import datetime, timezone
from pathlib import Path

ROOT = Path(__file__).resolve().parents[4]
HERE = Path(__file__).resolve().parent
OLD = ROOT / 'docs/evidence/m4-collapsed-residual-work'


def bind(path: Path) -> dict:
    raw = path.read_bytes()
    return {'path': str(path.relative_to(ROOT)), 'bytes': len(raw),
            'sha256': hashlib.sha256(raw).hexdigest()}


def json_write(path: Path, value: object) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open('x', encoding='utf-8') as stream:
        json.dump(value, stream, ensure_ascii=False, indent=2)
        stream.write('\n')


def main() -> None:
    target = HERE / 'baseline'
    target.mkdir()
    seal_path = ROOT / 'docs/evidence/m4-collapsed-residual-verification-sealed.json'
    seal = json.loads(seal_path.read_text())
    assert seal['productionBuild'] == 'index-Dzp9we5t.js'
    assert seal['bindingCount'] == 689
    assert bind(seal_path)['sha256'] == '43457fb22c7871466fa8563efd44525ccd5168a625312ad424c5c82536f34aa6'
    sealed = {item['path']: item for item in seal['bindings']}
    specs: list[tuple[Path, Path, str, str]] = []
    cases: list[dict] = []
    for level in range(3):
        for preset in ['paper', 'monochrome']:
            for width in [85, 180]:
                case = f'cnn-level{level}-{preset}-{width}'
                files = [
                    ('browser-after-union', 'document.json'),
                    ('browser-after-union', 'saved-envelope.json'),
                    ('browser-after-union', 'figure.svg'),
                    ('browser-after-union', 'figure.svg.receipt.json'),
                    ('browser-after-union', 'export-binding.json'),
                    ('browser-after-union', 'fit-before.json'),
                    ('browser-after-union', 'fit-after.json'),
                    ('core-after-union', 'scene.json'),
                    ('core-after-union', 'export.scene.json'),
                    ('core-after-union', 'publication.svg'),
                    ('core-after-union', 'interactive.svg'),
                ]
                for family, filename in files:
                    source = OLD / family / case / filename
                    copy = target / 'cnn12' / case / family / filename
                    specs.append((source, copy, case, f'{family}/{filename}'))
                cases.append({'caseId': case, 'level': level, 'preset': preset,
                              'widthMm': width})
    # Literal expected role membership and source/port facts for all four edge
    # roles come from these actual historical model documents. Their old pixels
    # do not certify the new renderer or human readability.
    for name in ['transformer-level0-paper-180', 'transformer-level1-paper-180',
                 'transformer-level2-paper-180', 'transformer-level3-paper-180']:
        for filename in ['canvas.json', 'scene.json', 'public.svg']:
            source = OLD / 'acceptance/baseline' / f'{name}.{filename}'
            specs.append((source, target / 'historical-transformer' / source.name,
                          name, f'historical/{filename}'))
    for source in sorted((ROOT / 'studio/src/core').glob('*.ts')):
        specs.append((source, target / 'provenance' / source.relative_to(ROOT),
                      'provenance', source.name))
    for relative in [
        'studio/dist/index.html', 'studio/dist/assets/index-Dzp9we5t.js',
        'studio/dist/assets/index-B6WbMowt.css',
        'docs/evidence/m4-collapsed-residual-work/acceptance/oracle.ts',
        'docs/evidence/m4-collapsed-residual-work/core-observation-run-attempt-2/receipt.json',
        'docs/evidence/m4-collapsed-residual-work/checks/suite-attempt-3/receipt.json',
        'docs/evidence/m4-collapsed-residual-work/checks/build-attempt-2/receipt.json',
    ]:
        source = ROOT / relative
        specs.append((source, target / 'provenance' / relative,
                      'provenance', relative))
    inputs = [source for source, _, _, _ in specs] + [seal_path, Path(__file__).resolve()]
    before = [bind(path) for path in inputs]
    for source, _, _, _ in specs:
        actual = bind(source)
        assert actual == sealed[actual['path']], f'Unsealed/changed baseline {source}'
    records = []
    for source, copy, case, key in specs:
        raw = source.read_bytes()
        copy.parent.mkdir(parents=True, exist_ok=True)
        with copy.open('xb') as stream:
            stream.write(raw)
        assert source.read_bytes() == copy.read_bytes()
        records.append({'caseId': case, 'key': key, 'source': bind(source), 'copy': bind(copy)})
    after = [bind(path) for path in inputs]
    assert before == after, 'Baseline changed during capture'
    result = {
        'protocol': 'archcanvas-monochrome-role-independent-baseline/1',
        'capturedAt': datetime.now(timezone.utc).isoformat(),
        'expectedSource': 'Existing actual frozen artifact bytes and independent literal contracts; no product calls.',
        'priorSeal': bind(seal_path), 'priorBindingCount': 689,
        'cases': cases, 'records': records, 'inputsBefore': before,
        'inputsAfter': after, 'inputsUnchanged': True,
        'dependenciesInstalled': False, 'userModelsExecuted': False,
        'limits': 'Historical Transformer references establish only prior source facts and geometry. This capture performs no new browser, pixel, performance or human acceptance.',
    }
    json_write(target / 'capture.json', result)
    print(json.dumps({'cases': len(cases), 'files': len(records), 'capture': bind(target / 'capture.json'),
                      'inputsUnchanged': True}))


if __name__ == '__main__':
    main()
