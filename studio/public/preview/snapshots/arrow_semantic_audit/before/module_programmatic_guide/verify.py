#!/usr/bin/env python3
"""Verify final module source evidence, semantic guards, SVG and PNG exports."""
import bootstrap
import argparse,importlib,json
from pathlib import Path
from verify import source_checks,exported_view
from registry import KEYS,VIEWS
HERE=Path(__file__).resolve().parent

def main():
    parser=argparse.ArgumentParser(description=__doc__)
    parser.add_argument('generated',type=Path,nargs='?',default=HERE/'generated')
    parser.add_argument('--module',choices=['all']+KEYS,default='all');parser.add_argument('--png',action='store_true')
    args=parser.parse_args();reports={}
    for key in KEYS if args.module=='all' else [args.module]:
        folder=args.generated/key
        ir=json.loads((folder/'semantic_ir.json').read_text());ev=json.loads((folder/'source_evidence.json').read_text())
        try:
            assert ir['artifact_scope']=='module' and ir['profile']['artifact_scope']=='module'
            source=source_checks(folder,ev,ir,manifest_path=HERE/'source_manifest.json',source_root=HERE/'sources')
            labels=importlib.import_module('module_adapters.'+key).validate_ir(ir);assert labels
            views={}
            for i,view in enumerate(VIEWS,1):
                lay=json.loads((folder/f'layout_{view}.json').read_text())
                views[view]=exported_view(folder/f'figure{i}_{view}.svg',lay,ev,ir,png=args.png)
            reports[key]=dict(passed=True,source=source,semantic_checks=labels,views=views)
            print(key+': PASS')
        except (AssertionError,ValueError,KeyError) as exc:
            reports[key]=dict(passed=False,error=str(exc));print(key+': FAIL '+str(exc))
    filename='export_checks.json' if args.module=='all' else 'export_checks_'+args.module+'.json'
    passed=all(r['passed'] for r in reports.values());result=dict(passed=passed,artifact_scope='module',modules=reports,model_executed=False)
    (args.generated/filename).write_text(json.dumps(result,ensure_ascii=False,indent=2)+'\n')
    if not passed:raise SystemExit(1)

if __name__=='__main__':main()
