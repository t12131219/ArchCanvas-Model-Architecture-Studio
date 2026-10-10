"""Reproduce static PatchTST import, source-draft edit, and exact save/reopen."""
from copy import deepcopy
import json
from pathlib import Path
import subprocess
import sys
import tempfile

PROJECT = Path(__file__).resolve().parents[3]
sys.path.insert(0, str(PROJECT / 'src'))
from archcanvas_python import analyze_project
from archcanvas_authoring.source_import import import_editable_source_draft
from archcanvas_cli.drafts import DraftStore
from archcanvas_cli.server import DocumentStore

NODE = r"""
import {createDocument,createHistory,reduceHistory,buildScene} from './studio/src/core/index.ts';
import {projectSourceEditing} from './studio/src/sourceEditingProjection.ts';
import {sameSourceSemantics,sourcePresentationOperations} from './studio/src/sourcePresentation.ts';
import {renderSvg} from './studio/src/core/svg.ts';
let raw=''; for await(const chunk of process.stdin) raw+=chunk;
const v=JSON.parse(raw);
if(v.action==='view'){
 const d=createDocument(v.architecture),e=projectSourceEditing(d);
 process.stdout.write(JSON.stringify([d,buildScene(d),e.document,e.scene]));
}else{
 const before=v.draft,after=structuredClone(before);
 const n=after.nodes.find(n=>after.sourceProvenance.nodeRefs[n.id].evidence==='opaque');
 if(!n)throw new Error('No explicit opaque boundary');
 n.label='Configuration-dependent region';n.position.x+=23;after.revision++;
 if(!sameSourceSemantics(before,after))throw new Error('Unexpected semantic change');
 const history=reduceHistory(createHistory(v.document),{type:'apply',operations:sourcePresentationOperations(v.document,before,after)});
 if(!renderSvg(buildScene(history.document)).includes(n.label))throw new Error('Export lost alias');
 const undo=reduceHistory(history,{type:'undo'}),redo=reduceHistory(undo,{type:'redo'});
 if(JSON.stringify(redo.document.layout)!==JSON.stringify(history.document.layout))throw new Error('Redo lost layout');
 process.stdout.write(JSON.stringify({draft:after,history,svgExport:'passed',undoRedo:'passed'}));
}
"""

def node(value):
    result = subprocess.run(['node', '--experimental-strip-types', '--input-type=module', '-e', NODE],
        cwd=PROJECT, input=json.dumps(value), capture_output=True, text=True, check=True, timeout=45)
    return json.loads(result.stdout)

root = Path(sys.argv[1]).resolve()
architecture = analyze_project(root, 'models.PatchTST:Model')
view = node({'action': 'view', 'architecture': architecture})
before = import_editable_source_draft(*view)['draft']
edited = node({'action': 'edit', 'document': view[0], 'draft': before})
assert edited['history']['document']['architecture'] == architecture
assert edited['draft']['sourceProvenance'] == before['sourceProvenance']
with tempfile.TemporaryDirectory(prefix='archcanvas-patchtst-evidence-') as directory:
    drafts = DraftStore(Path(directory) / 'drafts')
    saved = drafts.put(before['id'], edited['draft'], 0)
    assert drafts.get(before['id']) == saved
    canvases = DocumentStore(Path(directory) / 'documents')
    history = edited['history']
    saved_canvas = canvases.put(view[0]['id'], history['document'], 0, history=history)
    assert canvases.get(view[0]['id']) == saved_canvas
    assert saved_canvas['document']['sourceBindingDigest'] == architecture['sourceDigest']
print(json.dumps({'model': 'supplied PatchTST', 'root': str(root), 'entry': 'models.PatchTST:Model',
    'nodes': len(architecture['nodes']), 'edges': len(architecture['edges']),
    'opaque': sum(n['evidence'] == 'opaque' for n in architecture['nodes']),
    'configuration': 'not supplied; no branch invented',
    'editableDraftSaveReopen': 'passed', 'sameCanvasEditSaveReopen': 'passed',
    'sourceDigest': architecture['sourceDigest'], 'irDigest': architecture['irDigest'],
    'sourceDigestUnchanged': True, 'svgExport': edited['svgExport'], 'undoRedo': edited['undoRedo'],
    'modelExecution': False}, indent=2))
