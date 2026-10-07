"""Seal finite validator-stage materials after documentation is finalized."""
from pathlib import Path
import hashlib
import json

stage = Path(__file__).resolve().parent
root = stage.parents[2]
assert (stage / 'entry-update-work/document-seal-final-attempt-1/manifest.json').is_file()
excluded = {stage / 'manifest.json', stage / 'stage-seal-readback.json'}
paths = {p for p in stage.rglob('*') if p.is_file() and p not in excluded}
paths.update(root / p for p in ['scripts/validate_input_observation.mjs',
    'scripts/validate_continuous_observation.mjs', 'tests/m4_input_observation.test.mjs',
    'tests/m4_continuous_projection_independent.test.mjs', 'docs/m4-continuous-proxy-correction.md',
    'docs/m4-performance.md', 'docs/evidence/README.md', 'docs/evidence/m4-current-gate-audit.json'])
for report_name, key in [('independent-report.json', 'bindings'),
                         ('replay-attempt-1/report.json', 'inputBindings')]:
    report = json.loads((stage / report_name).read_text())
    paths.update(root / p['path'] for p in report[key])


def binding(path):
    data = path.read_bytes()
    return {'path': str(path.relative_to(root)), 'bytes': len(data),
            'sha256': hashlib.sha256(data).hexdigest()}


bindings = [binding(p) for p in sorted(paths)]
manifest = {'schema': 'archcanvas-continuous-proxy-finite-material-seal/1',
    'bindings': bindings, 'scope': 'Listed validator/test/document-stage materials and replay inputs only; not a full runtime dependency inventory or new browser/performance/human certification.'}
target = stage / 'manifest.json'
with target.open('x') as f:
    json.dump(manifest, f, ensure_ascii=False, indent=2)
    f.write('\n')
failures = [b['path'] for b in bindings if binding(root / b['path']) != b]
result = {'schema': 'archcanvas-continuous-proxy-finite-material-readback/1',
    'total': len(bindings), 'exact': len(bindings) - len(failures), 'failures': failures,
    'manifestSha256': hashlib.sha256(target.read_bytes()).hexdigest(),
    'scope': 'Byte readback only; no tests rerun.'}
with (stage / 'stage-seal-readback.json').open('x') as f:
    json.dump(result, f, indent=2)
    f.write('\n')
print(json.dumps(result, indent=2))
raise SystemExit(1 if failures else 0)
