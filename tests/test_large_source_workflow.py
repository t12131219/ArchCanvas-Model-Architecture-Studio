"""Large unfamiliar source model: bounded HTTP import/edit/save/reopen contracts."""
import json
from copy import deepcopy
from pathlib import Path
import subprocess
import tempfile
import threading
import unittest
from urllib.request import build_opener,ProxyHandler,Request
from archcanvas_python import analyze_source
from archcanvas_cli.server import ArchCanvasServer,DocumentStore
from archcanvas_cli.persistence import encode_envelope

ROOT=Path(__file__).resolve().parents[1]
SOURCE='''from torch import nn
class Leaf(nn.Module):
 def __init__(self):
  super().__init__(); self.proj=nn.Linear(7,7); self.act=nn.GELU()
 def forward(self,x): return self.act(self.proj(x))
class Stem(nn.Module):
 def __init__(self):
  super().__init__(); self.units=nn.ModuleList([Leaf() for i in range(16)])
 def forward(self,x):
  for unit in self.units: x=unit(x)
  return x
class Grove(nn.Module):
 def __init__(self):
  super().__init__(); self.stems=nn.ModuleList([Stem() for i in range(16)])
 def forward(self,x):
  for stem in self.stems: x=stem(x)
  return unknown_finish(x)
raise RuntimeError("model must not execute")
'''
class LargeSourceWorkflow(unittest.TestCase):
 def test_large_unseen_source_can_import_save_reopen_and_retain_multiple_canvas_undo_steps(self):
  architecture=analyze_source(SOURCE,'model:Grove')
  self.assertGreater(len(architecture['nodes']),800)
  script="""import fs from 'node:fs';import {createDocument,buildScene} from './src/core/index.ts';import {projectSourceEditing} from './src/sourceEditingProjection.ts';const a=JSON.parse(fs.readFileSync(0,'utf8'));const d=createDocument(a),e=projectSourceEditing(d);process.stdout.write(JSON.stringify({document:d,scene:buildScene(d),editingDocument:e.document,editingScene:e.scene}));"""
  rendered=subprocess.run(['node','--experimental-strip-types','--input-type=module','-e',script],cwd=ROOT/'studio',input=json.dumps(architecture),capture_output=True,text=True,timeout=45,check=True)
  payload=json.loads(rendered.stdout)
  with tempfile.TemporaryDirectory() as directory:
   try: server=ArchCanvasServer(('127.0.0.1',0),data_dir=Path(directory))
   except PermissionError: self.skipTest('Loopback requires the permitted host regression environment.')
   thread=threading.Thread(target=server.serve_forever,daemon=True);thread.start()
   url=f'http://127.0.0.1:{server.server_address[1]}';client=build_opener(ProxyHandler({}))
   token=json.load(client.open(url+'/api/session'))['token']
   def call(path,value):
    request=Request(url+path,data=json.dumps(value,ensure_ascii=False,separators=(',',':')).encode(),headers={'Content-Type':'application/json','X-ArchCanvas-Session':token})
    with client.open(request,timeout=45) as response: return json.load(response)
   try:
    result=call('/api/authoring/import-source',payload);draft=result['draft']
    self.assertGreater(len(json.dumps(draft).encode()),4_000_000)
    original=deepcopy(draft);draft['nodes'][-1]['label']='Retained unknown boundary'
    saved=call('/api/authoring/drafts/'+draft['id'],{'draft':draft,'expectedRevision':0})
    reopened=json.load(client.open(url+'/api/authoring/drafts/'+draft['id']))
    self.assertEqual(reopened,saved);self.assertEqual(reopened['draft']['sourceProvenance'],original['sourceProvenance'])
    # Several large snapshots retain exact source facts while their stored
    # envelope contains one copy. No raising of the CanvasDocument 4 MB cap.
    document=payload['document']; history={'document':deepcopy(document),'past':[deepcopy(document) for i in range(5)],'future':[]}
    for index,snapshot in enumerate(history['past']): snapshot['revision']=index
    store=DocumentStore(Path(directory)/'large-canvas');store.put(document['id'],document,0,history=history)
    self.assertLess(store.path(document['id']).stat().st_size,4_000_000)
    self.assertEqual(store.get(document['id'])['history'],history)
    self.assertLess(len(json.dumps(encode_envelope({'document':document,'history':history}))),4_000_000)
   finally: server.shutdown();server.server_close();thread.join(2)
