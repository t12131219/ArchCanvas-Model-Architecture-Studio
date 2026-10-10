import json,tempfile,time
from pathlib import Path
from archcanvas_cli.drafts import DraftStore
from archcanvas_cli.server import DocumentStore
from archcanvas_cli.persistence import encode_envelope
from copy import deepcopy
v=json.loads(Path('/tmp/archcanvas-real-transformer-bridge.json').read_text())
draft=json.loads(Path('/tmp/archcanvas-real-transformer-draft.json').read_text())
with tempfile.TemporaryDirectory() as directory:
 store=DraftStore(Path(directory)/'drafts');saved=store.put(draft['id'],draft,0);assert store.get(draft['id'])==saved
 d=v[0];h={'document':deepcopy(d),'past':[deepcopy(d) for i in range(5)],'future':[]}
 for i,s in enumerate(h['past']):s['revision']=i
 canvases=DocumentStore(Path(directory)/'documents');canvases.put(d['id'],d,0,history=h);assert canvases.get(d['id'])['history']==h
 print(json.dumps({'source':'supplied original Transformer','nodes':len(draft['nodes']),'draftBytes':store.path(draft['id']).stat().st_size,'canvasHistoryBytes':canvases.path(d['id']).stat().st_size,'pastSnapshots':5,'draftSaveReopen':'passed','canvasSaveReopen':'passed','modelExecution':False}))
