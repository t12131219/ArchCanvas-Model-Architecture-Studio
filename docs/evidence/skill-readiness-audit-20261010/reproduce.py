import json
import os
from pathlib import Path
import subprocess
import sys
import tempfile
from unittest.mock import patch

ROOT = Path('/home/fzg/PycharmProjects/ArchCanvas/ArchCanvas_Model_Architecture_Studio')
sys.path[:0] = [str(ROOT / 'src'), str(ROOT / 'tests')]
from archcanvas_cli.server import ArchCanvasServer
from archcanvas_python import analyze_project
from test_authoring_http_independent import authored

out = {}
with tempfile.TemporaryDirectory(prefix='archcanvas-audit-storage-') as folder:
    base = Path(folder)
    # Only HTTP socket setup is replaced. Real server storage constructors run.
    def no_socket(self, address, handler):
        self.server_address = address
    with patch('http.server.ThreadingHTTPServer.__init__', no_socket):
        a = ArchCanvasServer(('127.0.0.1', 18765), data_dir=base/'alpha-documents')
        b = ArchCanvasServer(('127.0.0.1', 18766), data_dir=base/'beta-documents')
    draft = authored('draft-a1b2')
    draft['title'] = 'belongs-to-alpha'
    a.drafts.put(draft['id'], draft, 0)
    observed = b.drafts.get(draft['id'])
    out['storage'] = {
        'socketSetup': 'mocked; storage constructors and persistence are real',
        'documentDirectoriesDistinct': a.store.directory != b.store.directory,
        'workspaceDirectoriesEqual': a.workspace.directory == b.workspace.directory,
        'draftDirectoriesEqual': a.drafts.directory == b.drafts.directory,
        'betaReadsAlphaDraft': observed['draft']['title'] == 'belongs-to-alpha',
    }

with tempfile.TemporaryDirectory(prefix='archcanvas-audit-export-') as folder:
    base = Path(folder)
    architecture = base/'architecture.json'
    architecture.write_text(json.dumps(analyze_project(ROOT/'fixtures/mlp', 'model:MLP')))
    document = base/'document.json'
    js = '''import fs from 'node:fs';
import {createDocument} from './studio/src/core/index.ts';
fs.writeFileSync(process.argv[2], JSON.stringify(createDocument(JSON.parse(fs.readFileSync(process.argv[1])))));
'''
    subprocess.run(['node','--experimental-strip-types','--input-type=module','-e',js,str(architecture),str(document)], cwd=ROOT, check=True, capture_output=True)
    artifact = base/'figure.svg'
    artifact.write_text('last-good-artifact')
    Path(str(artifact)+'.receipt.json').mkdir()
    completed = subprocess.run(['node','scripts/export_canvas.mjs','--document',str(document),'--output',str(artifact),'--python',str(ROOT/'.venv/bin/python')], cwd=ROOT, capture_output=True, text=True)
    out['export'] = {
        'failureInjected': 'receipt path is an existing directory',
        'returncode': completed.returncode,
        'stderr': completed.stderr.strip(),
        'priorArtifactPreserved': artifact.read_text() == 'last-good-artifact',
        'newArtifactIsSvg': '<svg' in artifact.read_text(),
    }

destination = Path('/tmp/archcanvas-skill-audit-20261010/reproductions.json')
destination.write_text(json.dumps(out, ensure_ascii=False, indent=2))
print(destination.read_text())
