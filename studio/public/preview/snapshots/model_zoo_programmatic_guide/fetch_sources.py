#!/usr/bin/env python3
"""Restore only manifest-pinned model sources; no upstream code runs or weights download."""
from __future__ import annotations
import argparse
import ast
import hashlib
import json
from pathlib import Path
import urllib.request
from notebook_source import extract

HERE=Path(__file__).resolve().parent


def main():
    parser=argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--out',type=Path,default=HERE/'sources')
    args=parser.parse_args()
    manifest=json.loads((HERE/'source_manifest.json').read_text())
    for slug,project in manifest.items():
        for member,pinned in project['files'].items():
            target=args.out/slug/member
            if target.is_file() and hashlib.sha256(target.read_bytes()).hexdigest()==pinned['sha256']:
                continue
            request=urllib.request.Request(pinned['url'],headers={'User-Agent':'ArchCanvas-pinned-source'})
            with urllib.request.urlopen(request,timeout=45) as response:data=response.read()
            if hashlib.sha256(data).hexdigest()!=pinned['sha256']:raise ValueError('Downloaded source differs from pinned snapshot: '+member)
            target.parent.mkdir(parents=True,exist_ok=True);target.write_bytes(data)
            print('Restored',slug+'/'+member)
        for member,pinned in project.get('derived',{}).items():
            notebook=json.loads((args.out/slug/pinned['original']).read_text())
            text,mapping=extract(notebook);ast.parse(text)
            if hashlib.sha256(text.encode()).hexdigest()!=pinned['sha256'] or mapping!=pinned['line_map']:
                raise ValueError('Notebook transformation differs from reviewed source: '+member)
            target=args.out/slug/member;target.parent.mkdir(parents=True,exist_ok=True);target.write_text(text)
    print('Pinned sources verified. No model code was imported or executed.')


if __name__=='__main__':main()
