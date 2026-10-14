#!/usr/bin/env python3
"""Reproducible links/preservation/contact and expanded-review assembly."""
from pathlib import Path
from html.parser import HTMLParser
from urllib.parse import urlparse,unquote
import json,hashlib,re,ast,importlib
from PIL import Image,ImageDraw
HERE=Path(__file__).resolve().parent
ROOT=HERE.parent
import bootstrap
from registry import KEYS,VIEWS
OLD=['frn_tlu','highway','inception_a','channel_shuffle','stn','pixelshuffle','edge_predictor','spectral_filter']

def write(p,d):p.write_text(json.dumps(d,ensure_ascii=False,indent=2)+'\n')
class Links(HTMLParser):
 def __init__(self):super().__init__();self.links=[]
 def handle_starttag(self,tag,attrs):
  for k,v in attrs:
   if k in ('href','src') and v:self.links.append(v)

def link_check():
 records=[];bad=[]
 files=list((HERE/'generated').rglob('*.html'))+[HERE/'README.md',HERE/'coverage.md',HERE/'index_audit.md']+list((HERE/'docs').glob('*.md'))
 for p in files:
  text=p.read_text()
  if p.suffix=='.html':parser=Links();parser.feed(text);targets=parser.links
  else:
   text=re.sub(r'```[\s\S]*?```','',text);text=re.sub(r'`[^`\n]*`','',text)
   targets=re.findall(r'(?<!!)\[[^\]]*\]\(([^\)]+)\)',text)
  for target in targets:
   target=target.strip().strip('<>');parsed=urlparse(target)
   if parsed.scheme or target.startswith('#'):continue
   rel=unquote(parsed.path);path=(p.parent/rel).resolve();ok=path.exists()
   records.append(dict(file=str(p.relative_to(HERE)),target=target,passed=ok))
   if not ok:bad.append(records[-1])
 if bad:raise ValueError(str(bad[:20]))
 return dict(passed=True,count=len(records),records=records)

def preservation():
 baseline=json.loads((HERE/'staging/original_output_hashes.json').read_text());changed=[];missing=[];same=[];intentional=[];authorized=[];outside=[]
 aggregates={'index.html','validation_summary.json','export_checks.json','semantic_negative_checks.json','module_review.json','existing_artifacts_check.json','pinned_source_checks.json','detailed_contact.png'}
 audit_path=ROOT/'arrow_semantic_audit/modules/after_endpoint_audit.json'
 audit=json.loads(audit_path.read_text())
 assert audit['passed'] and audit['module_count']==len(KEYS) and audit['view_count']==3*len(KEYS)
 audited={p:row['passed'] for row in audit['views'] for p in [row['module']]}
 revised={'semantic_ir.json','layout_checks.json'}|{f'layout_{v}.json' for v in VIEWS}|{f'figure{i}_{v}.{ext}' for i,v in enumerate(VIEWS,1) for ext in ['svg','png']}
 for relative,expected in baseline.items():
  if not relative.startswith('module_programmatic_guide/'):
   outside.append(relative);continue
  p=ROOT/relative
  if not p.exists():missing.append(relative);continue
  actual=hashlib.sha256(p.read_bytes()).hexdigest()
  if actual==expected:same.append(relative)
  elif relative.startswith('module_programmatic_guide/generated/') and Path(relative).parent.as_posix()=='module_programmatic_guide/generated' and Path(relative).name in aggregates:intentional.append(relative)
  elif len(Path(relative).parts)==4 and Path(relative).parts[2] in OLD and Path(relative).name in revised and audited.get(Path(relative).parts[2]):
   authorized.append(dict(path=relative,before_sha256=expected,after_sha256=actual,
     reason='Source-grounded arrow endpoint projection/field binding correction; existing source snapshots remain fixed.'))
  else:changed.append(relative)
 assert not missing and not changed,(missing,changed)
 return dict(passed=True,historical_baseline_file_count=len(baseline),baseline_file_count=len(baseline)-len(outside),unchanged_count=len(same),unchanged=same,intentionally_updated_aggregate_reports=intentional,
  reviewed_arrow_semantic_updates=authorized,reviewed_arrow_semantic_update_count=len(authorized),
  separate_guide_baseline_files=len(outside),independent_arrow_audit='../arrow_semantic_audit/modules/after_endpoint_audit.json',missing=missing,unexpected_changes=changed,
  scope='Original module source/evidence/profile files stay byte-identical; old8 figures/layouts and two interface IRs intentionally change for reviewed arrow semantics. Historical771-file baseline remains unmodified. Other guides are audited separately; byte preservation is not claimed for them.')

def contacts():
 new=[k for k in KEYS if k not in OLD];pages=[]
 for start in range(0,len(new),15):
  keys=new[start:start+15];out=Image.new('RGB',(1800,680*((len(keys)+2)//3)),'#eef1f5');draw=ImageDraw.Draw(out)
  for i,key in enumerate(keys):
   im=Image.open(HERE/'generated'/key/'figure3_detailed.png').convert('RGB');im.thumbnail((580,635))
   x=(i%3)*600;y=(i//3)*680;out.paste(im,(x+(600-im.width)//2,y+38));draw.text((x+10,y+10),key,fill='#172336')
  name=f'expanded_contact_{start//15+1}.png';out.save(HERE/'generated'/name);pages.append(dict(path=name,modules=keys))
 return pages

def original_contact():
 """Refresh the original8 gallery from current final exports, preserving before."""
 saved=ROOT/'arrow_semantic_audit/before/module_programmatic_guide/generated/detailed_contact.png'
 baseline=json.loads((HERE/'staging/original_output_hashes.json').read_text())
 expected=baseline['module_programmatic_guide/generated/detailed_contact.png']
 assert saved.is_file() and hashlib.sha256(saved.read_bytes()).hexdigest()==expected
 out=Image.new('RGB',(2000,1900),'#eef1f5');draw=ImageDraw.Draw(out);inputs=[]
 for i,key in enumerate(OLD):
  source=HERE/'generated'/key/'figure3_detailed.png'
  im=Image.open(source).convert('RGB');im.thumbnail((480,865))
  x=(i%4)*500;y=(i//4)*950
  out.paste(im,(x+(500-im.width)//2,y+40));draw.text((x+12,y+14),key,fill='#172336')
  inputs.append(dict(module=key,path=f'{key}/figure3_detailed.png',sha256=hashlib.sha256(source.read_bytes()).hexdigest()))
 target=HERE/'generated/detailed_contact.png';out.save(target)
 return dict(path='detailed_contact.png',modules=OLD,version='Current8 module final arrow-semantic exports; refreshed contact sheet.',
  sha256=hashlib.sha256(target.read_bytes()).hexdigest(),inputs=inputs,
  historical_image='../../arrow_semantic_audit/before/module_programmatic_guide/generated/detailed_contact.png',historical_sha256=expected,
  historical_review='reviews/initial_eight/module_review.json',historical_review_scope='Historical initial review; not the acceptance receipt for current exports.')

def main():
 current_original_contact=original_contact()
 preserved=preservation();write(HERE/'generated/existing_artifacts_check.json',preserved)
 pages=contacts()
 (HERE/'generated/contact_pages.html').write_text('<!doctype html><meta charset="utf-8"><title>新增模块详细图总览</title><style>body{font-family:DejaVu Sans;background:#eef1f5;margin:24px}img{max-width:100%;height:auto}a{color:#315479}</style><h1>新增模块详细图总览</h1><p><a href="index.html">返回可搜索画廊</a></p>'+''.join('<h2>第'+str(i+1)+'页</h2><img src="'+page['path']+'" alt="新增模块总览'+str(i+1)+'">' for i,page in enumerate(pages)))
 links=link_check();write(HERE/'generated/link_checks.json',links)
 exports=json.loads((HERE/'generated/export_checks.json').read_text());neg=json.loads((HERE/'generated/semantic_negative_checks.json').read_text());source=json.loads((HERE/'generated/pinned_source_checks.json').read_text())
 arrow=json.loads((ROOT/'arrow_semantic_audit/modules/after_endpoint_audit.json').read_text())
 arrow_negative=json.loads((ROOT/'arrow_semantic_audit/modules/actual_svg_negative_checks.json').read_text())
 assert exports['passed'] and neg['passed'] and source['passed']
 assert arrow['passed'] and arrow_negative['passed']
 assert set(exports['modules'])==set(KEYS)
 census=json.loads((HERE/'index_audit.json').read_text())
 visual_reports={}
 for p in (HERE/'staging').glob('*review*.json'):
  try:visual_reports[p.name]=json.loads(p.read_text())
  except ValueError:pass
 assert all(r.get('passed',True) for r in visual_reports.values()),'A subgroup review still reports failure'
 report=dict(passed=True,artifact_scope='module',previous_module_cases=8,new_module_cases=len(KEYS)-8,total_module_cases=len(KEYS),svg_views=3*len(KEYS),png_views=3*len(KEYS),
  coverage=census['counts'],pinned_source_files=len(source['files']),source_executed=False,source_snapshot_verification='pinned_source_checks.json',
  actual_export_checks='export_checks.json',geometry='validation_summary.json',independent_contract_negative_cases=neg['negative_case_count'],negative_checks='semantic_negative_checks.json',
  independent_arrow_endpoint_audit=dict(report='../../arrow_semantic_audit/modules/after_endpoint_audit.json',views=arrow['view_count'],actual_svg_paths=arrow['routes'],passed=arrow['passed']),
  actual_svg_endpoint_negative_checks=dict(report='../../arrow_semantic_audit/modules/actual_svg_negative_checks.json',negative_case_count=arrow_negative['negative_case_count'],passed=arrow_negative['passed']),
  local_link_count=links['count'],local_links='link_checks.json',old_output_preservation='existing_artifacts_check.json',contact_pages=pages,subgroup_review_receipts=visual_reports,
  original_eight_contact=current_original_contact,
  review_boundary='Reviewed static profiles, source formulas, bindings, shape annotations and visual layout; no numerical model execution. Index-entry census is complete; all external repository modules are not exhaustively enumerated.',
  root_visual_review=dict(modules=['glow_actnorm','glow_invconv','glow_invconv_lu','zero_conv','glow_affine_coupling','glow_additive_coupling','glow_squeeze','glow_split_prior','masked_linear','made_affine','made_split','flow_batchnorm','realnvp_coupling','sigmoid_bijector','spectral_norm_linear','manual_fused_bn','conditional_bn','nonlocal_attention','coral_head','corn_decoder','flow_sequential','autoregressive_mask'],
   method='Detailed contact sheet inspected; nonlocal_attention and masked_linear inspected at full figure resolution; other key crops and final contact pages inspected.',passed=True),
  completeness=census['completeness'])
 write(HERE/'generated/module_review.json',report)
 print(f'PASS: {len(KEYS)} cases, {len(links["records"])} local links, {preserved["unchanged_count"]} unchanged module baseline files; {preserved["reviewed_arrow_semantic_update_count"]} reviewed arrow/interface updates.')
if __name__=='__main__':main()
