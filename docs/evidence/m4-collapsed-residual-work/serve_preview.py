"""Serve a separate formal Studio regression session on a fresh loopback port."""
from pathlib import Path
import hashlib
import json
import sys

import archcanvas_cli
import archcanvas_cli.server
from archcanvas_cli.server import ArchCanvasServer

ROOT = Path(__file__).resolve().parents[3]
DATA = ROOT / '.archcanvas/m4-collapsed-residual-session/documents'


def fingerprint(path):
    body = path.read_bytes()
    return {'path': str(path), 'bytes': len(body), 'sha256': hashlib.sha256(body).hexdigest()}


for module in [archcanvas_cli, archcanvas_cli.server]:
    assert Path(module.__file__).resolve().is_relative_to(ROOT / 'src'), module.__file__
assert Path(sys.prefix).resolve() == (ROOT / '.venv').resolve()
with ArchCanvasServer(('127.0.0.1', 0), data_dir=DATA, studio_dir=ROOT / 'studio/dist') as server:
    print(json.dumps({
        'url': f'http://127.0.0.1:{server.server_address[1]}/',
        'dataDirectory': str(DATA), 'pythonExecutable': sys.executable,
        'resolvedPythonExecutable': str(Path(sys.executable).resolve()),
        'packageOrigins': [str(Path(module.__file__).resolve()) for module in [archcanvas_cli, archcanvas_cli.server]],
        'studioAssets': [fingerprint(path) for path in sorted((ROOT / 'studio/dist').rglob('*')) if path.is_file()],
        'scope': 'Separate loopback session; static fixture analysis and visual document/export only. No model execution or dependency installation.',
    }, ensure_ascii=False), flush=True)
    server.serve_forever()
