from pathlib import Path
import json,time
from copy import deepcopy
from urllib.request import build_opener,ProxyHandler,Request
from archcanvas_cli.persistence import encode_envelope
client=build_opener(ProxyHandler({}));url='http://127.0.0.1:8879';token=json.load(client.open(url+'/api/session'))['token']
def call(path,value,method='POST'):
 data=json.dumps(value,ensure_ascii=False,separators=(',',':')).encode()
 request=Request(url+path,data=data,method=method,headers={'Content-Type':'application/json','X-ArchCanvas-Session':token})
 with client.open(request,timeout=60) as response:return json.load(response)
v=json.loads(Path('/tmp/archcanvas-real-transformer-bridge.json').read_text()); t=time.monotonic()
result=call('/api/authoring/import-source',dict(zip(['document','scene','editingDocument','editingScene'],v)))
draft=result['draft'];draft['nodes'][-1]['label']='Original Transformer output'
saved=call('/api/authoring/drafts/'+draft['id'],{'draft':draft,'expectedRevision':0})
assert json.load(client.open(url+'/api/authoring/drafts/'+draft['id']))==saved
rebased=call('/api/authoring/source-frontier',{'draft':draft,'document':v[2],'scene':v[3],'viewDocument':v[0],'viewScene':v[1]})
assert rebased['draft']['id']==draft['id']
document=v[0];history={'document':document,'past':[deepcopy(document) for i in range(5)],'future':[]}
for i,snapshot in enumerate(history['past']):snapshot['revision']=i
saved_canvas=call('/api/documents/'+document['id'],encode_envelope({'document':document,'history':history,'expectedRevision':0}),'PUT')
read=json.load(client.open(url+'/api/documents/'+document['id']))
assert read['history']==history
print(json.dumps({'runtime':'current checkout','nodes':len(draft['nodes']),'draftBytes':len(json.dumps(draft).encode()),'HTTPImport':'passed','HTTPDraftSaveReopen':'passed','HTTPSourceFrontierRebase':'passed','HTTPCompressedCanvasSaveReopen':'passed','historySnapshots':5,'seconds':time.monotonic()-t,'sourceDigest':document['sourceBindingDigest'],'irDigest':document['architecture']['irDigest'],'modelExecution':False}))
