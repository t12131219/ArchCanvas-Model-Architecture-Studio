import sys,json,hashlib,urllib.request,ast
from pathlib import Path
ROOT=Path(__file__).resolve().parents[1];sys.path.insert(0,str(ROOT));import bootstrap
from notebook_source import extract
HEADERS={'User-Agent':'ArchCanvas-static-source-module-coverage'}
def get(url):
 with urllib.request.urlopen(urllib.request.Request(url,headers=HEADERS),timeout=45) as response:return response.read()
def acquire(repo,slug,wanted,commit=None,tree_path=None):
 up=ROOT/'upstream';up.mkdir(exist_ok=True)
 if commit is None:commit=json.loads(get('https://api.github.com/repos/'+repo+'/commits/HEAD'))['sha']
 tree=json.loads(Path(tree_path).read_text()) if tree_path else json.loads(get('https://api.github.com/repos/'+repo+'/git/trees/'+commit+'?recursive=1'))
 entries={e['path']:e for e in tree['tree'] if e['type']=='blob'}
 if 'LICENSE' not in wanted:
  licenses=[p for p in entries if p.lower() in ['license','license.md','license.txt','copying']]
  wanted+=licenses[:1]
 files={};derived={}
 for path in wanted:
  if path not in entries:raise ValueError(repo+' missing '+path)
  url=f'https://raw.githubusercontent.com/{repo}/{commit}/{path}';data=get(url)
  blob=hashlib.sha1(b'blob '+str(len(data)).encode()+b'\0'+data).hexdigest()
  if blob!=entries[path]['sha']:raise ValueError('Git blob mismatch')
  p=ROOT/'sources'/slug/path;p.parent.mkdir(parents=True,exist_ok=True);p.write_bytes(data)
  files[path]=dict(url=url,sha256=hashlib.sha256(data).hexdigest(),bytes=len(data),git_blob_sha=blob)
  if path.endswith('.ipynb'):
   text,mapping=extract(json.loads(data));ast.parse(text);member=path[:-6]+'.py';q=ROOT/'sources'/slug/member;q.write_text(text)
   derived[member]=dict(original=path,sha256=hashlib.sha256(text.encode()).hexdigest(),line_map=mapping,transformation='Concatenate code cells in order; annotate boundaries; comment IPython commands; never execute.')
  elif path.endswith('.py'):ast.parse(data)
 revision=dict(repository=repo,repository_url='https://github.com/'+repo,commit=commit)
 (up/(slug+'_revision.json')).write_text(json.dumps(revision,indent=2)+'\n');(up/(slug+'_tree.json')).write_text(json.dumps(tree,indent=2)+'\n')
 return revision|dict(ref=commit,files=files,derived=derived,license_files=[p for p in files if p.lower().startswith('license')],license_status='saved' if any(p.lower().startswith('license') for p in files) else 'no repository license file found; no licensing assertion')
if __name__=='__main__':
 out=ROOT/'staging/root_source_manifest.json';m=json.loads(out.read_text()) if out.exists() else {}
 jobs=[('rosinality/glow-pytorch','glow-modules',['model.py']),('ikostrikov/pytorch-flows','density-flow-modules',['flows.py']),('ajbrock/BigGAN-PyTorch','biggan-modules',['layers.py']),('rasbt/deeplearning-models','rasbt-ordinal-modules',['pytorch_ipynb/ordinal/CORAL_cement.ipynb','pytorch_ipynb/ordinal/CORN_cement.ipynb'])]
 for repo,slug,wanted in jobs:
  if slug in m:continue
  if slug=='rasbt-ordinal-modules':p=acquire(repo,slug,wanted,'59beda3aa25337e576564f1c18c6edd26f9f30e3',ROOT.parent/'model_zoo_programmatic_guide/catalog/upstream/deeplearning-models/tree.json')
  else:p=acquire(repo,slug,wanted)
  m[slug]=p;out.write_text(json.dumps(m,ensure_ascii=False,indent=2)+'\n');print(slug,p['commit'],list(p['files']),flush=True)
