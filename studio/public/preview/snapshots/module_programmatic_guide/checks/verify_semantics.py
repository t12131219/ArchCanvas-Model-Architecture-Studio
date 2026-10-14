#!/usr/bin/env python3
"""Repeat offline semantic contracts and intentionally incorrect diagram mutations."""
import argparse,importlib,json,sys
from pathlib import Path
HERE=Path(__file__).resolve().parents[1]
sys.path.insert(0,str(HERE))

def rejected_cases(value):
    if isinstance(value,dict):
        if 'negative_cases' in value:return value['negative_cases']
        return [case for child in value.values() for case in rejected_cases(child)]
    if isinstance(value,list):return [case for child in value for case in rejected_cases(child)]
    return []

def main():
    p=argparse.ArgumentParser(description=__doc__);p.add_argument('--report',type=Path,default=HERE/'generated/semantic_negative_checks.json')
    a=p.parse_args();reports={}
    for name in ['frn_highway','inception_shuffle','spatial_modules','graph_modules'] + [p.stem for p in sorted((HERE/'checks').glob('*_extended.py'))]:
        reports[name]=importlib.import_module(name).run()
        if not reports[name]['passed']:raise AssertionError(name+' failed')
    negatives=rejected_cases(reports)
    assert negatives and all(case['rejected'] for case in negatives)
    report=dict(passed=True,groups=reports,negative_case_count=len(negatives),model_executed=False,limitation='Contracts target reviewed module profiles, not arbitrary changed implementations.')
    a.report.parent.mkdir(parents=True,exist_ok=True);a.report.write_text(json.dumps(report,ensure_ascii=False,indent=2)+'\n')
    print(f'PASS: module contract groups and {len(negatives)} rejected semantic mutations.')
if __name__=='__main__':main()
