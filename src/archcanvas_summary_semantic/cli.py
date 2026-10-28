"""python -m archcanvas_summary_semantic.cli: static analysis and explicit CPU probe."""
import argparse
import json
from pathlib import Path
from .analyzer import analyze
from .sources import inventory
from .schema import validate_ir, digest
from .probe import observe
from .merge import merge


def save(path, value):
    path = Path(path); path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(value, ensure_ascii=False, indent=2, allow_nan=False) + '\n')


def publish(ir_path, catalog_path):
    ir_path, catalog_path = Path(ir_path), Path(catalog_path)
    ir = json.loads(ir_path.read_text())
    validation = validate_ir(ir)
    if not validation['ok']: raise ValueError(validation)
    catalog = json.loads(catalog_path.read_text()) if catalog_path.exists() else {'schema': 'semantic-studio/1', 'models': []}
    identity = digest(ir['entry'])[:16]
    asset = ir_path.resolve().relative_to(catalog_path.parent.resolve()).as_posix()
    descriptor = {'id': identity, 'title': ir['title'], 'ir': asset, 'source': ir['entry'], 'digest': ir['ir_digest'],
                  'nodes': len(ir['nodes']), 'edges': len(ir['edges']), 'motifs': len(ir['motifs']),
                  'runtime': ir['runtime']['status'], 'coverage': ir['coverage']['status']}
    catalog['models'] = [m for m in catalog['models'] if m['id'] != identity] + [descriptor]
    save(catalog_path, catalog)
    return descriptor


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    commands = parser.add_subparsers(dest='command', required=True)
    scan = commands.add_parser('inventory'); scan.add_argument('--root', action='append', required=True); scan.add_argument('--output', required=True)
    build = commands.add_parser('analyze'); build.add_argument('--source', required=True); build.add_argument('--entry', required=True)
    build.add_argument('--factory', action='store_true', help='analyze an explicit effect-free factory returning the model')
    build.add_argument('--project-root', help='bounded root for local source imports; never executes imports')
    build.add_argument('--cell', type=int); build.add_argument('--constructor', default='{}'); build.add_argument('--output', required=True)
    build.add_argument('--probe-spec'); build.add_argument('--interpreter'); build.add_argument('--source-root'); build.add_argument('--timeout', type=int, default=45)
    build.add_argument('--catalog', help='optional semantic studio catalog path (explicit publication)')
    check = commands.add_parser('validate'); check.add_argument('ir')
    register = commands.add_parser('publish'); register.add_argument('ir'); register.add_argument('--catalog', required=True)
    args = parser.parse_args()
    if args.command == 'inventory':
        value = inventory(args.root); save(args.output, value)
        print(json.dumps({'models': len(value['models']), 'github_links': len(value['github_links']), 'diagnostics': len(value['diagnostics']), 'model_executed': False})); return
    if args.command == 'validate':
        result = validate_ir(json.loads(Path(args.ir).read_text())); print(json.dumps(result)); raise SystemExit(0 if result['ok'] else 2)
    if args.command == 'publish':
        print(json.dumps(publish(args.ir, args.catalog), ensure_ascii=False)); return
    constructor = json.loads(args.constructor)
    spec = json.loads(Path(args.probe_spec).read_text()) if args.probe_spec else None
    if spec:
        if args.factory: parser.error('--factory is static-only; runtime requires a class entry')
        if not args.interpreter: parser.error('--probe-spec requires explicit --interpreter')
        if constructor and constructor != spec.get('constructor', {}): parser.error('constructor conflicts with probe specification')
        constructor = spec.get('constructor', {})
    ir = analyze(args.source, args.entry, constructor, args.cell, project_root=args.project_root or args.source_root, factory_entry=args.factory)
    if spec: ir = merge(ir, observe(args.source, args.entry, spec, args.interpreter, args.source_root, args.timeout))
    validation = validate_ir(ir)
    if not validation['ok']: raise ValueError(validation)
    save(args.output, ir)
    if args.catalog:
        publish(args.output, args.catalog)
    print(json.dumps({'output': args.output, 'nodes': len(ir['nodes']), 'edges': len(ir['edges']), 'motifs': len(ir['motifs']),
                      'opaque': sum(n['kind'] == 'opaque' for n in ir['nodes']), 'runtime': ir['runtime']['status'], 'coverage': ir['coverage']['status']}, ensure_ascii=False))
    if spec and ir['runtime']['status'] != 'passed': raise SystemExit(2)


if __name__ == '__main__': main()
