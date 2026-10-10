"""Source provenance survives JSON.stringify without accepting changed facts."""
from copy import deepcopy
import json
from pathlib import Path
import subprocess
import tempfile
import unittest

from archcanvas_authoring import DraftError, validate_draft
from archcanvas_authoring.draft import _digest
from archcanvas_authoring.source_import import import_editable_source_draft
from archcanvas_cli.drafts import DraftStore
from archcanvas_python import analyze_source

ROOT = Path(__file__).resolve().parents[1]


class SourceNumericRoundtripTests(unittest.TestCase):
    def test_browser_number_roundtrip_preserves_unknown_model_and_rejects_changed_facts(self):
        architecture = analyze_source('''from torch import nn
class Tidal(nn.Module):
 def __init__(self):
  super().__init__(); self.drop=nn.Dropout(p=0.0)
 def forward(self,x): return unknown_wave(self.drop(x))
raise RuntimeError("drawing must never execute the model")
''', 'model:Tidal')
        script = """import fs from 'node:fs';import {createDocument,buildScene} from './studio/src/core/index.ts';import {projectSourceEditing} from './studio/src/sourceEditingProjection.ts';const d=createDocument(JSON.parse(fs.readFileSync(0,'utf8'))),e=projectSourceEditing(d);process.stdout.write(JSON.stringify([d,buildScene(d),e.document,e.scene]));"""
        result = subprocess.run(['node', '--experimental-strip-types', '--input-type=module', '-e', script],
            cwd=ROOT, input=json.dumps(architecture), capture_output=True, text=True, check=True, timeout=45)
        original = import_editable_source_draft(*json.loads(result.stdout))['draft']
        facts = original['sourceProvenance']['architecture']['nodes']
        index = next(i for i, n in enumerate(facts) if n['kind'] == 'Dropout')
        self.assertIs(type(facts[index]['parameters']['p']), float)
        old = deepcopy(original)
        old['sourceProvenance']['digest'] = _digest({k: v for k, v in old['sourceProvenance'].items() if k != 'digest'})
        validate_draft(old)  # Frozen receipts stay readable with their own bytes.
        result = subprocess.run(['node', '-e', "let s='';for await(const c of process.stdin)s+=c;const d=JSON.parse(s);d.nodes.find(n=>d.sourceProvenance.nodeRefs[n.id].evidence==='opaque').label='Retained unknown wave';process.stdout.write(JSON.stringify(d));"],
            input=json.dumps(original), capture_output=True, text=True, check=True, timeout=10)
        returned = json.loads(result.stdout)
        self.assertIs(type(returned['sourceProvenance']['architecture']['nodes'][index]['parameters']['p']), int)
        self.assertEqual(returned['sourceProvenance'], original['sourceProvenance'])
        self.assertEqual(returned['sourceProvenance']['digest'], original['sourceProvenance']['digest'])
        with tempfile.TemporaryDirectory() as directory:
            store = DraftStore(Path(directory))
            saved = store.put(returned['id'], returned, 0)
            self.assertEqual(store.get(returned['id']), saved)
            for value in (0.25, False, '0'):
                changed = deepcopy(returned)
                changed['sourceProvenance']['architecture']['nodes'][index]['parameters']['p'] = value
                with self.assertRaisesRegex(DraftError, 'provenance digest changed'):
                    store.put(changed['id'], changed, 1)
                self.assertEqual(store.get(returned['id']), saved)
