import sys,json,hashlib,ast,subprocess,tempfile
from pathlib import Path
ROOT=Path(__file__).resolve().parents[1];sys.path.insert(0,str(ROOT));import bootstrap
from notebook_source import extract

def acquire(repo,slug,wanted):
 clone=Path('/tmp')/('archcanvas-src-'+slug)
 if not (clone/'.git').exists():subprocess.run(['git','clone','--depth','1','--filter=blob:none','--no-checkout','https://github.com/'+repo+'.git',str(clone)],check=True)
 def git(*args):return subprocess.check_output(['git','-C',str(clone),*args])
 commit=git('rev-parse','HEAD').decode().strip();entries=[]
 for line in git('ls-tree','-r','HEAD').decode().splitlines():
  meta,path=line.split('\t',1);mode,kind,sha=meta.split();entries.append(dict(path=path,mode=mode,type=kind,sha=sha))
 idx={e['path']:e for e in entries};files={};derived={}
 licenses=[p for p in idx if p.lower() in ['license','license.md','license.txt','copying']];wanted+=licenses[:1]
 for path in wanted:
  data=git('show',commit+':'+path);blob=hashlib.sha1(b'blob '+str(len(data)).encode()+b'\0'+data).hexdigest();assert blob==idx[path]['sha']
  p=ROOT/'sources'/slug/path;p.parent.mkdir(parents=True,exist_ok=True);p.write_bytes(data)
  files[path]=dict(url=f'https://raw.githubusercontent.com/{repo}/{commit}/{path}',sha256=hashlib.sha256(data).hexdigest(),bytes=len(data),git_blob_sha=blob)
  if path.endswith('.py'):ast.parse(data)
  if path.endswith('.ipynb'):
   text,mapping=extract(json.loads(data));ast.parse(text);member=path[:-6]+'.py';(ROOT/'sources'/slug/member).write_text(text)
   derived[member]=dict(original=path,sha256=hashlib.sha256(text.encode()).hexdigest(),line_map=mapping,transformation='Concatenate code cells in order; annotate boundaries; comment IPython commands; never execute.')
 revision=dict(repository=repo,repository_url='https://github.com/'+repo,commit=commit)
 (ROOT/'upstream'/(slug+'_revision.json')).write_text(json.dumps(revision,indent=2)+'\n');(ROOT/'upstream'/(slug+'_tree.json')).write_text(json.dumps(dict(sha=commit,tree=entries,truncated=False,acquisition='git ls-tree pinned fetched commit'),indent=2)+'\n')
 return revision|dict(ref=commit,files=files,derived=derived,license_files=licenses[:1],license_status='saved' if licenses else 'no root repository license file found')
if __name__=='__main__':
 out=ROOT/'staging/root_source_manifest.json';m=json.loads(out.read_text()) if out.exists() else {}
 for repo,slug,wanted in [('rosinality/glow-pytorch','glow-modules',['model.py']),('ikostrikov/pytorch-flows','density-flow-modules',['flows.py']),('ajbrock/BigGAN-PyTorch','biggan-modules',['layers.py'])]:
  if slug in m:continue
  m[slug]=acquire(repo,slug,wanted);out.write_text(json.dumps(m,ensure_ascii=False,indent=2)+'\n');print(slug,m[slug]['commit'],list(m[slug]['files']),flush=True)
