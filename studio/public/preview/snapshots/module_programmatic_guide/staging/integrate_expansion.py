"""Merge reviewed new snapshots and module records, without rewriting old modules."""
from pathlib import Path
import json,sys,importlib
HERE=Path(__file__).resolve().parents[1]
sys.path.insert(0,str(HERE))
import bootstrap
base=json.loads((HERE/'source_manifest.json').read_text())
for f in ['root_source_manifest.json','vision_source_manifest.json','graph_source_manifest.json','sequence_source_manifest.json']:
 for slug,record in json.loads((HERE/'staging'/f).read_text()).items():
  if slug in base:
   assert base[slug]==record,('Existing project digest would change',slug)
  else:base[slug]=record
(HERE/'source_manifest.json').write_text(json.dumps(base,ensure_ascii=False,indent=2)+'\n')
catalog=json.loads((HERE/'module_catalog.json').read_text());records=catalog['modules'];keys={x['key'] for x in records}
for f in ['root_catalog.json','vision_catalog.json','graph_catalog.json','sequence_catalog.json']:
 p=HERE/'staging'/f
 if not p.exists():continue
 data=json.loads(p.read_text());data=data['modules'] if isinstance(data,dict) else data
 for record in data:
  key=record['key']
  if key in keys:
   current=next(r for r in records if r['key']==key);current.update(record)
  else:records.append(record);keys.add(key)
for record in records:
 record.setdefault('profile',{}).setdefault('model_executed',False)
 record['profile'].setdefault('artifact_scope','module')
 if 'directory_provenance' not in record:
  cp=record['catalog_provenance'];idx='deeplearning-models' if cp['repository'].startswith('rasbt/') else 'Awesome-pytorch-list';line=cp['readme_line'];text=(HERE/'upstream'/idx/'README.md').read_text().splitlines()[line-1]
  record['directory_provenance']=dict(index=idx,commit=cp['commit'],line=line,readme_path='upstream/'+idx+'/README.md',text=text,url='https://github.com/'+cp['repository']+'/blob/'+cp['commit']+'/README.md#L'+str(line),relationship=cp['selection'])
 if 'sources'  in record and 'name' in record:continue
 model=importlib.import_module('module_adapters.'+record['key']).build()
 record.update(name=model['name'],artifact_scope='module',scope=model['module_scope'],profile=model['profile'],documentation='docs/'+model['doc'],gallery='generated/'+record['key']+'/index.html',status='reviewed_module_adapter')
 record.setdefault('previous_coverage','not_drawn_as_this_selected_module_subgraph')
 record.setdefault('existing_comparison','已有普通 Conv/Linear、残差、注意力与基本图传播；未分别画出本例所选依赖、状态与参数身份组合。')
 record.setdefault('new_adaptation',record.get('new_value','; '.join(model['facts'][:2])))
 sources=[]
 for member,symbols in model['symbols'].items():
  slug,inner=member.split('/',1);p=base[slug];derived=p.get('derived',{}).get(inner);raw=derived['original'] if derived else inner
  pinned=derived or p['files'][inner]
  sources.append(dict(local_path='sources/'+member,repository=p['repository'],commit=p['commit'],symbols=symbols,raw_path=raw,url='https://github.com/'+p['repository']+'/blob/'+p['commit']+'/'+raw,sha256=pinned['sha256'],derived_from_notebook=bool(derived)))
 record['sources']=sources
catalog['modules']=records;catalog['counts']=dict(module_cases=len(records),primary_svg_views=3*len(records),primary_png_views=3*len(records))
catalog['scope']='Reviewed local module subgraphs from frozen directory-linked source implementations; not all models or all symbols in all external repositories.'
(HERE/'module_catalog.json').write_text(json.dumps(catalog,ensure_ascii=False,indent=2)+'\n')
(HERE/'registry.py').write_text('"""Module-only examples, separately counted from whole models."""\nKEYS='+repr([r['key'] for r in records])+"\nVIEWS=['overview','modules','detailed']\nFAMILIES="+repr({r['key']:r['family'] for r in records})+'\n')
print('Integrated',len(records),'cases and',len(base),'source snapshots')
