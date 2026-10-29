#!/usr/bin/env python3
"""Build the shipped source library using the same extraction as project imports."""
import copy
import hashlib
import json
import sys
from pathlib import Path
PROJECT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(PROJECT / 'src'))
from archcanvas_preview.component_library import *
DATA = PROJECT / 'studio/public/preview/data/semantic'
OUTPUT = PROJECT / 'studio/public/preview/data/source-components'

def build(data=DATA, output=OUTPUT):
    catalog = json.loads((data / 'studio-catalog.json').read_text())
    groups = {}
    total = 0
    for model in catalog['models']:
        raw = (data / model['ir']['path']).read_bytes()
        if hashlib.sha256(raw).hexdigest() != model['ir']['sha256']:
            raise ValueError('Catalog IR hash mismatch: ' + model['id'])
        ir = json.loads(raw)
        for node in candidates(ir):
            total += 1
            module = extract(ir, node)
            family, variant = fingerprints(module)
            group = groups.setdefault(family, dict(names=set(), aliases=set(), category='模块' if node['kind'] == 'composite' else '算子', variants={}))
            group['names'].add(module['title'])
            original_name = node.get('source_class') or node.get('framework_type') or node.get('function_target') or node['label']
            group['aliases'].add(original_name)
            record = group['variants'].setdefault(variant, dict(module=module, origins=[]))
            record['origins'].append(dict(model=model['id'], title=model['title'].split(' · ')[0], node=node['id'],
                                          label=node['label'], irSha256=model['ir']['sha256'], source=copy.deepcopy(node.get('source', []))))
    output.mkdir(parents=True, exist_ok=True)
    named, files = {}, set()
    for family, group in sorted(groups.items()):
        names = sorted(group['names'], key=lambda x: (len(x), x))
        family_id = 'family-' + digest([group['category'], names[0]])[:24]
        entry = named.setdefault(family_id, dict(id=family_id, title=names[0], aliases=set(), category=group['category'], variants=[]))
        entry['aliases'].update(names[1:])
        entry['aliases'].update(group['aliases'] - {names[0]})
        for variant, record in sorted(group['variants'].items()):
            module, origins = record['module'], record['origins']
            ident = 'src-' + variant[:24]
            origin_refs = [{**o, 'source': [{k: v for k, v in s.items() if k != 'expression'} for s in o['source']]} for o in origins]
            module['sourceLibrary'] = dict(schema=SCHEMA, id=ident, family=family_id, structure=family, fingerprint=variant, origins=origin_refs)
            content = packed(module) + b'\n'
            path = ident + '.json'
            files.add(path)
            (output / path).write_bytes(content)
            configuration = []
            for n in module['ir']['nodes']:
                if n.get('constructor'):
                    config = dict(component=short_name(n), constructor=n['constructor'])
                    if config not in configuration:
                        configuration.append(config)
            entry['variants'].append(dict(id=ident, structure=family, path=path, bytes=len(content), sha256=hashlib.sha256(content).hexdigest(),
                                 nodes=len(module['ir']['nodes']), edges=len(module['ir']['edges']),
                                 constructor=module['constructor'], occurrences=len(origins),
                                 configuration=configuration,
                                 sources=sorted({o['title'] for o in origins})))
    families = list(named.values())
    for f in families:
        f['aliases'] = sorted(f['aliases'])
        f['variants'].sort(key=lambda v: (v['nodes'], v['id']))
    families.sort(key=lambda f: (f['category'], f['title'].casefold(), f['id']))
    result = dict(schema=SCHEMA, matching='ordered-graph-facts/1',
                  stats=dict(candidates=total, families=len(families), structures=len(groups), variants=sum(len(f['variants']) for f in families),
                             models=len(catalog['models'])), families=families)
    (output / 'index.json').write_bytes(packed(result) + b'\n')
    for old in output.glob('src-*.json'):
        if old.name not in files:
            old.unlink()
    return result


if __name__ == '__main__':
    print(json.dumps(build()['stats'], ensure_ascii=False))
