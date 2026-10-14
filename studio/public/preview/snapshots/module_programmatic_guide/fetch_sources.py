#!/usr/bin/env python3
"""Verify or restore manifest-pinned module source snapshots; never execute them."""
import bootstrap
import argparse,ast,hashlib,json,urllib.request
from pathlib import Path
from notebook_source import extract
HERE=Path(__file__).resolve().parent

def verify_sources(out,offline=False):
    manifest=json.loads((HERE/'source_manifest.json').read_text());records=[]
    for slug,project in manifest.items():
        for member,pinned in project['files'].items():
            target=out/slug/member
            valid=target.is_file() and hashlib.sha256(target.read_bytes()).hexdigest()==pinned['sha256']
            if not valid:
                if offline:raise ValueError('Missing or modified pinned source: '+str(target))
                request=urllib.request.Request(pinned['url'],headers={'User-Agent':'ArchCanvas-pinned-module-source'})
                with urllib.request.urlopen(request,timeout=45) as response:data=response.read()
                if hashlib.sha256(data).hexdigest()!=pinned['sha256']:raise ValueError('Remote snapshot differs: '+member)
                target.parent.mkdir(parents=True,exist_ok=True);target.write_bytes(data)
            data=target.read_bytes()
            gitsha=hashlib.sha1(b'blob '+str(len(data)).encode()+b'\0'+data).hexdigest()
            if gitsha!=pinned['git_blob_sha']:raise ValueError('Git blob mismatch: '+member)
            records.append(dict(path=slug+'/'+member,sha256=pinned['sha256'],git_blob_sha=gitsha,passed=True))
        for member,pinned in project.get('derived',{}).items():
            raw=json.loads((out/slug/pinned['original']).read_text());text,mapping=extract(raw);ast.parse(text)
            if hashlib.sha256(text.encode()).hexdigest()!=pinned['sha256'] or mapping!=pinned['line_map']:
                raise ValueError('Notebook transformation changed: '+member)
            target=out/slug/member
            if offline:
                if not target.is_file() or target.read_bytes()!=text.encode():raise ValueError('Derived snapshot changed: '+member)
            else:target.parent.mkdir(parents=True,exist_ok=True);target.write_text(text)
            records.append(dict(path=slug+'/'+member,sha256=pinned['sha256'],notebook_cell_map=True,ast_parsed=True,passed=True))
    return dict(passed=True,files=records,model_executed=False)

def main():
    p=argparse.ArgumentParser(description=__doc__);p.add_argument('--out',type=Path,default=HERE/'sources')
    p.add_argument('--offline',action='store_true',help='Only validate saved snapshots; no network or rewrites')
    p.add_argument('--report',type=Path);a=p.parse_args();report=verify_sources(a.out,a.offline)
    if a.report:a.report.parent.mkdir(parents=True,exist_ok=True);a.report.write_text(json.dumps(report,indent=2)+'\n')
    print(f'PASS: {len(report["files"])} pinned/derived files; no upstream code executed.')
if __name__=='__main__':main()
