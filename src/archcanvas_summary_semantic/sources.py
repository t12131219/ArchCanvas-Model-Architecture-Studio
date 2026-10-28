"""Read .py and notebook cells as data; never run imports or notebook setup."""
import ast
import json
import re
from pathlib import Path
from .schema import digest


def units(path):
    path = Path(path).resolve()
    raw = path.read_bytes()
    if len(raw) > 8_000_000:
        raise ValueError('source file exceeds 8 MB: ' + str(path))
    if path.suffix == '.py':
        values = [(None, raw.decode('utf-8-sig'))]
    elif path.suffix == '.ipynb':
        data = json.loads(raw)
        values = [(i, ''.join(c.get('source', []))) for i, c in enumerate(data.get('cells', [])) if c.get('cell_type') == 'code']
    else:
        raise ValueError('only .py and .ipynb inputs are supported')
    result, diagnostics = [], []
    for cell, text in values:
        logical = str(path) + (f'#cell={cell}' if cell is not None else '')
        try:
            tree = ast.parse(text, filename=logical)
        except SyntaxError as exc:
            diagnostics.append({'file': logical, 'kind': 'syntax-unavailable', 'line': exc.lineno, 'reason': exc.msg})
            continue
        result.append({'path': logical, 'physical': str(path), 'cell': cell, 'sha256': digest(raw),
                       'unit_sha256': digest(text.encode()), 'text': text, 'tree': tree})
    return result, diagnostics


def inventory(roots, max_files=2000):
    models, links, diagnostics, files = [], [], [], []
    for root in map(lambda p: Path(p).resolve(), roots):
        if not root.is_dir():
            diagnostics.append({'file': str(root), 'kind': 'missing-root'})
            continue
        candidates = sorted(p for p in root.rglob('*') if p.is_file() and p.suffix in {'.py', '.ipynb', '.md'} and not any(part in {'.git', 'node_modules', '.venv', '__pycache__'} for part in p.relative_to(root).parts))
        if len(candidates) > max_files:
            diagnostics.append({'file': str(root), 'kind': 'inventory-truncated', 'maximum': max_files})
        for path in candidates[:max_files]:
            files.append({'path': str(path), 'sha256': digest(path.read_bytes())})
            if path.suffix == '.md':
                for url in sorted(set(re.findall(r'https://github\.com/[\w.-]+/[\w.-]+', path.read_text(errors='replace')))):
                    links.append({'url': url, 'source': str(path), 'status': 'link-only; not downloaded or executed'})
                continue
            us, ds = units(path)
            diagnostics.extend(ds)
            for u in us:
                for cls in u['tree'].body:
                    if isinstance(cls, ast.ClassDef) and any(isinstance(m, ast.FunctionDef) and m.name in {'forward', '__call__'} for m in cls.body):
                        models.append({'file': str(path), 'cell': u['cell'], 'entry': cls.name,
                                       'line': cls.lineno, 'source_sha256': u['sha256'], 'bases': [ast.unparse(b) for b in cls.bases], 'status': 'static-candidate'})
    return {'schema': 'semantic-source-inventory/1', 'read_only': True, 'model_executed': False,
            'roots': list(map(str, roots)), 'files': files, 'models': models, 'github_links': links, 'diagnostics': diagnostics}
