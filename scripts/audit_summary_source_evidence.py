"""Read-only hash, AST and source-span audit; never imports/executes a model."""
import ast
import hashlib
import json
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
BASE = ROOT / 'studio/public/preview/data/semantic'
OUT = ROOT / 'docs/evidence/summary-all-cases-progressive-20261028/source-evidence-audit.json'
rows = []
for model in json.loads((BASE / 'studio-catalog.json').read_text())['models']:
    ir = json.loads((BASE / model['ir']['path']).read_text())
    units, sources, issues = {}, [], []
    for source in ir.get('sources', []):
        physical = Path(source.get('physical') or source['path'].split('#cell=')[0])
        row = {'path': source['path'], 'physical': str(physical)}
        if not physical.is_file():
            row['available'] = False
            sources.append(row)
            issues.append('Missing source: ' + str(physical))
            continue
        raw = physical.read_bytes()
        row.update(available=True, fileHashMatches=hashlib.sha256(raw).hexdigest() == source.get('sha256'))
        cell = source.get('cell')
        text = ''.join(json.loads(raw)['cells'][cell]['source']) if cell is not None else raw.decode('utf-8')
        units[source['path']] = text
        row['unitHashMatches'] = hashlib.sha256(text.encode()).hexdigest() == source.get('unit_sha256')
        try:
            tree = ast.parse(text)
            row['astParsed'] = True
            row['astNodes'] = sum(1 for _ in ast.walk(tree))
        except SyntaxError as exc:
            row.update(astParsed=False, syntax=str(exc))
        if not row['fileHashMatches'] or not row['unitHashMatches']:
            issues.append('Source hash mismatch: ' + source['path'])
        sources.append(row)
    checked = 0
    for node in ir['nodes']:
        for evidence in node.get('source', []):
            text = units.get(evidence.get('file'))
            if text is None:
                continue
            start, end = evidence.get('line'), evidence.get('end_line')
            if start is not None:
                checked += 1
                if not 1 <= start <= (end or start) <= len(text.splitlines()):
                    issues.append('Out-of-range span: ' + node['id'])
    rows.append({'id': model['id'], 'title': model['title'], 'sources': sources, 'nodeSpansChecked': checked, 'issues': sorted(set(issues))})
    print(model['title'], 'sources', len(sources), 'spans', checked, 'issues', len(set(issues)))
OUT.write_text(json.dumps({'schema': 'summary-source-evidence-audit/1', 'executesModel': False, 'models': rows}, ensure_ascii=False, indent=2) + '\n')
