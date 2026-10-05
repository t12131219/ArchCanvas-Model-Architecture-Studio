"""Copy newly observed inputs before the UI saves another revision."""
from pathlib import Path
import subprocess

root = Path(__file__).resolve().parents[3]
work = Path(__file__).resolve().parent
for raw in sorted((work / 'raw').iterdir()):
    case = raw.name
    if (work / 'cases' / case).exists():
        continue
    command = [
        str(root / '.venv/bin/python'), str(root / 'scripts/prepare_hierarchy_matrix_capture.py'),
        'case', '--matrix', str(root / '.archcanvas/browser-visual-matrix-hierarchy-final'),
        '--store', str(root / '.archcanvas/m4-hierarchy-matrix/documents'),
        '--raw', str(raw / 'dom-observation.json'),
        '--browser-scene', str(raw / 'browser-scene.svg'),
        '--screenshot', str(raw / 'screenshot.jpg'), '--output', str(work / 'cases' / case),
    ]
    if (raw / 'actual-document-store.json').exists():
        command += ['--saved-envelope', str(raw / 'actual-document-store.json')]
    result = subprocess.run(command, capture_output=True, text=True)
    (work / 'helper-cli-results' / f'{case}.txt').write_text(result.stdout + result.stderr)
    print(case, result.returncode)
    if result.returncode:
        print(result.stderr)
        raise SystemExit(result.returncode)
