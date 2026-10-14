"""CLI for a new adapter before central registry/manifest merge."""
from pathlib import Path
import sys
HERE=Path(__file__).resolve().parents[1];sys.path.insert(0,str(HERE))
import bootstrap
import argparse,importlib,json,hashlib,tempfile,subprocess
from evidence import collect,semantic_ir
from layout import render,validate
from theme import configure
from verify import source_checks,exported_view

def preview(key,partial,out,png=True):
 manifest=json.loads((HERE/'source_manifest.json').read_text())
 if partial:
  for slug,p in json.loads(Path(partial).read_text()).items():
   if slug in manifest:
    assert manifest[slug]['commit']==p['commit']
    manifest[slug]['files'].update(p['files']);manifest[slug].setdefault('derived',{}).update(p.get('derived',{}))
   else:manifest[slug]=p
 out=Path(out)/key;out.mkdir(parents=True,exist_ok=True)
 with tempfile.TemporaryDirectory(prefix='module-preview-') as tmp:
  mp=Path(tmp)/'manifest.json';mp.write_text(json.dumps(manifest))
  a=importlib.import_module('module_adapters.'+key);m=a.build();configure(m)
  ev=collect(m,HERE/'sources',out,manifest_path=mp);ir=semantic_ir(m,ev);a.validate_ir(ir)
  digest=hashlib.sha256(json.dumps(ir,sort_keys=True).encode()).hexdigest();records=[]
  for i,v in enumerate(['overview','modules','detailed']):
   svg=out/f'figure{i+1}_{v}.svg';lay=render(m,ev,ir,i,svg);lay['semantic_ir_sha256']=digest
   check=validate(lay);(out/f'layout_{v}.json').write_text(json.dumps(lay,ensure_ascii=False,indent=2)+'\n')
   if png:subprocess.run(['rsvg-convert',str(svg),'-o',str(svg.with_suffix('.png'))],check=True)
   if not check['passed']:raise AssertionError(check)
   exported_view(svg,lay,ev,ir,png=png);records.append(dict(view=v,canvas=lay['canvas'],passed=True))
  source=source_checks(out,ev,ir,manifest_path=mp,source_root=HERE/'sources')
 for filename,data in [('semantic_ir.json',ir),('source_evidence.json',ev),('preview_checks.json',dict(passed=True,views=records,source=source))]:
  (out/filename).write_text(json.dumps(data,ensure_ascii=False,indent=2)+'\n')
 print(key,[(v['view'],v['canvas']) for v in records],'PASS',flush=True)
 return dict(passed=True,views=records,source=source)
if __name__=='__main__':
 p=argparse.ArgumentParser();p.add_argument('key');p.add_argument('--manifest',type=Path);p.add_argument('--out',type=Path,required=True);p.add_argument('--svg-only',action='store_true');a=p.parse_args();preview(a.key,a.manifest,a.out,not a.svg_only)
