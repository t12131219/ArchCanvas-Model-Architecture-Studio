#!/usr/bin/env python3
"""Copy the explicitly authorized Summary model catalog; never a runtime dependency."""
import argparse
import hashlib
import json
from pathlib import Path


def vendor(source: Path, project: Path) -> dict:
    source = source.resolve()
    target = project / 'studio/public/preview/data/semantic'
    catalog = json.loads((source / 'data/semantic/catalog.json').read_text())
    if catalog.get('schema') != 'semantic-studio/1':
        raise ValueError('Unsupported Summary catalog')
    models, files, seen = [], {}, set()

    def copy_asset(relative: str) -> dict:
        path = Path(relative)
        if path.is_absolute() or '..' in path.parts or path.suffix != '.json':
            raise ValueError('Invalid catalog asset path')
        src = source / 'data/semantic' / path
        if not src.resolve().is_relative_to(source / 'data/semantic'):
            raise ValueError('Asset escapes semantic directory')
        data = src.read_bytes()
        dst = target / path
        dst.parent.mkdir(parents=True, exist_ok=True)
        dst.write_bytes(data)
        asset = dict(path=relative, bytes=len(data), sha256=hashlib.sha256(data).hexdigest())
        files[relative] = dict(path='data/semantic/' + relative, destination=str(dst.relative_to(project)), **{k:v for k,v in asset.items() if k!='path'})
        return asset

    copy_asset('catalog.json')
    for model in catalog['models']:
        identity = model['id']
        if not isinstance(identity, str) or identity in seen:
            raise ValueError('Invalid or duplicated model identity')
        seen.add(identity)
        asset = copy_asset(model['ir'])
        ir = json.loads((target / model['ir']).read_text())
        if ir.get('schema') != 'archcanvas-source-semantic/2' or ir.get('ir_digest') != model['digest'] or len(ir['nodes']) != model['nodes'] or len(ir['edges']) != model['edges']:
            raise ValueError('Catalog metadata disagrees with IR: ' + identity)
        presentation = copy_asset(model['presentation']) if model.get('presentation') else None
        models.append(dict(id=identity,title=model['title'],nodes=model['nodes'],edges=model['edges'],digest=model['digest'],runtime=model.get('runtime'),coverage=model.get('coverage'),ir=asset,presentation=presentation))
    result=dict(schema='archcanvas-summary-catalog/1',limits=dict(bytes=16000000,nodes=4000,edges=5000),models=models)
    (target/'studio-catalog.json').write_text(json.dumps(result,ensure_ascii=False,indent=2)+'\n')
    manifest=dict(schema='archcanvas-summary-catalog-assets/1',source='prototype/Summary_Merge',reason='Complete generic model catalog and referenced original IR/presentation assets; current runtime budget remains explicit',files=list(files.values()),models=len(models))
    (project/'docs/summary-catalog-assets-manifest-20261028.json').write_text(json.dumps(manifest,ensure_ascii=False,indent=2)+'\n')
    return manifest


if __name__ == '__main__':
    parser=argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--source',type=Path,required=True)
    args=parser.parse_args()
    result=vendor(args.source,Path(__file__).resolve().parents[1])
    print(json.dumps(dict(models=result['models'],assets=len(result['files']))))
