"""Frozen Git source and notebook AST evidence; upstream code is never imported."""
from __future__ import annotations
import ast
import hashlib
import json
from pathlib import Path

HERE=Path(__file__).resolve().parent


def digest(data):return hashlib.sha256(data).hexdigest()


def walk(tree):
    yield tree
    for child in tree.get('items',[]):yield from walk(child)


def symbols_in(source,filename,required=None):
    tree=ast.parse(source,filename=filename)
    # Explicit pseudo-symbol for notebook/module-level caller code. It denotes
    # the full AST module span, never an invented function or execution trace.
    tree.lineno=1
    tree.end_lineno=len(source.splitlines())
    symbols={'__module__':tree}
    def visit(body,prefix=''):
        for item in body:
            if isinstance(item,(ast.ClassDef,ast.FunctionDef,ast.AsyncFunctionDef)):
                key=prefix+item.name
                if key in symbols and (required is None or key in required):
                    raise ValueError('Ambiguous duplicate source symbol: '+key)
                symbols[key]=item
                if isinstance(item,ast.ClassDef):visit(item.body,key+'.')
    visit(tree.body)
    return symbols


def project_digest(project):
    files={path:record['sha256'] for path,record in project['files'].items()}
    files.update({path:record['sha256'] for path,record in project.get('derived',{}).items()})
    return digest(json.dumps(dict(repository=project['repository'],commit=project['commit'],files=files),sort_keys=True).encode())


def collect(model,source_root,out,manifest_path=None):
    manifest=json.loads(Path(manifest_path or HERE/'source_manifest.json').read_text())
    slug=model['source_project'];project=manifest[slug]
    projects={key:manifest[key] for key in [slug]+model.get('source_projects',[])}
    needed=set()
    for node in list(walk(model['tree']))+[n for aux in model.get('aux_inputs',[]) for n in walk(aux)]:
        needed.update(node['source'])
    for path,names in model.get('symbols',{}).items():needed.update(path+'::'+symbol for symbol in names)
    members={s.split('::')[0] for s in needed}|set(model.get('config_files',[]))
    members.update(key+'/'+name for key,p in projects.items() for name in p.get('license_files',[]))
    # Original notebooks accompany deterministic derived code for cell provenance.
    for member in list(members):
        key,inner=member.split('/',1);p=projects[key]
        if inner in p.get('derived',{}):members.add(key+'/'+p['derived'][inner]['original'])
    files={};spans={};notebook_origins={}
    for member in sorted(members):
        relative=Path(member)
        if relative.is_absolute() or '..' in relative.parts or relative.parts[0] not in projects:
            raise ValueError('Unsafe or foreign source path: '+member)
        project_slug=relative.parts[0];p=projects[project_slug]
        inner=relative.relative_to(project_slug).as_posix()
        derived=p.get('derived',{}).get(inner)
        pinned=derived or p['files'].get(inner)
        if not pinned:raise ValueError('Source not acquired/reviewed: '+member)
        data=(Path(source_root)/relative).read_bytes()
        if digest(data)!=pinned['sha256']:raise ValueError('Source changed; review adapter before drawing: '+member)
        source=data.decode('utf-8-sig');lines=source.splitlines()
        files[member]=dict(sha256=digest(data),lines=len(lines),
                           configuration_reference=member in model.get('config_files',[]),
                           url=p['files'][derived['original']]['url'] if derived else pinned['url'],
                           derived_from=project_slug+'/'+derived['original'] if derived else None)
        if len(projects)>1:files[member].update(source_project=project_slug,repository=p['repository'],commit=p['commit'])
        if member.endswith('.py'):
            required={s.split('::',1)[1] for s in needed if s.split('::',1)[0]==member}
            symbol_nodes=symbols_in(source,member,required=required)
            mapping={m['derived_line']:m for m in derived['line_map']} if derived else {}
            if derived:notebook_origins[member]=dict(original=project_slug+'/'+derived['original'],line_map=derived['line_map'],transformation=derived['transformation'])
            for name,item in symbol_nodes.items():
                symbol_key=member+'::'+name
                if symbol_key not in needed:continue
                origins=[mapping[line] for line in range(item.lineno,item.end_lineno+1) if line in mapping]
                spans[symbol_key]=dict(path=member,symbol=name,start=item.lineno,end=item.end_lineno,
                                 snippet='\n'.join(lines[item.lineno-1:item.end_lineno]),
                                 notebook_cells=sorted({m['cell_index'] for m in origins}),
                                 original_notebook=project_slug+'/'+derived['original'] if derived else None)
        target=out/'sources'/relative;target.parent.mkdir(parents=True,exist_ok=True);target.write_bytes(data)
    missing=needed-spans.keys()
    if missing:raise ValueError('Missing AST symbol(s): '+repr(sorted(missing)))
    for i,key in enumerate(sorted(spans),1):spans[key]['evidence_id']=f'E{i:03d}'
    result=dict(source_project=slug,repository=project['repository'],commit=project['commit'],
                source_snapshot_sha256=project_digest(project),entry=model['entry'],
                mode='static AST + reviewed explicit adapter; notebook/model code never executed',
                files=files,symbols=spans,notebook_origins=notebook_origins,
                license_files=[key+'/'+name for key,p in projects.items() for name in p.get('license_files',[])])
    if len(projects)>1:
        result['source_projects']={key:dict(repository=p['repository'],commit=p['commit'],snapshot=project_digest(p)) for key,p in projects.items()}
    return result


def semantic_ir(model,evidence):
    nodes=[];edges=[]
    def edge(src,dst,role='tensor',sp='out',dp='in'):
        edges.append(dict(id=f'{src}:{sp}->{dst}:{dp}:{role}',src=src,dst=dst,src_port=sp,dst_port=dp,role=role))
    def visit(node,parent=None):
        nodes.append({k:v for k,v in node.items() if k not in ('items','expand','width','fold_inline')}|
                     dict(parent=parent,source_evidence=[evidence['symbols'][s]['evidence_id'] for s in node['source']],ports=['in','out']))
        children=node.get('items',[])
        for child in children:visit(child,node['id'])
        if not children:return
        if node['mode']=='chain':
            if not node.get('suppress_input_boundary'):
                edge(node['id'],children[0]['id'],'shape_dependency' if node.get('input_role',node.get('boundary_input_role'))=='shape' else 'boundary','in','in')
            for a,b in zip(children,children[1:]):edge(a['id'],b['id'],node.get('flow_role','tensor'))
            edge(children[-1]['id'],node['id'],'boundary','out','out')
            if node.get('residual') or node.get('retained_input'):
                edge(node['id'],children[-1]['id'],'residual' if node.get('residual') else 'retained_input','in','side')
        elif node['mode']=='parallel':
            for i,child in enumerate(children):
                if node.get('semantic_mode')=='operand_bundle':
                    binding=node['child_inputs'][child['id']]
                    if binding['role']!='external':
                        edge(binding['producer'],child['id'],'shape_dependency' if binding['role']=='shape' else 'value_operand',binding.get('src_port','out'),'in')
                    edge(child['id'],node['id'],'operand_collection','out',f'operand[{i}]')
                else:
                    selector=child.get('input_selector',f'item[{i}]' if node.get('dispatch') else 'in')
                    edge(node['id'],child['id'],'dispatch' if node.get('dispatch') else 'fork',selector,'in')
                    edge(child['id'],node['id'],'tuple_collection','out',f'item[{i}]')
        elif node['mode']!='graph':
            raise ValueError('Unknown container mode: '+str(node['mode']))
        # A graph scope is containment only. It must not imply a chain, fork,
        # tuple collection, or tensor crossing its enclosing visual boundary.
    visit(model['tree'])
    for aux in model.get('aux_inputs',[]):visit(aux)
    for e in model.get('extra_edges',[]):edge(e['src'],e['dst'],e.get('role','tensor'),e.get('src_port','out'),e.get('dst_port','side'))
    index={n['id']:n for n in nodes}
    if len(index)!=len(nodes):raise ValueError('Duplicate node identity')
    for e in edges:
        for end in ('src','dst'):
            if e[end] not in index:raise ValueError('Unknown edge endpoint: '+e[end])
            if e[end+'_port'] not in index[e[end]]['ports']:index[e[end]]['ports'].append(e[end+'_port'])
    result=dict(schema='model-zoo-semantic-ir/1',model=model['key'],profile=model['profile'],
                source=dict(repository=evidence['repository'],commit=evidence['commit'],snapshot=evidence['source_snapshot_sha256']),
                nodes=nodes,edges=edges,facts=model['facts'],corrections=model['corrections'],
                semantics='reviewed static adapter; selected profile; explicit tuple/boundary edges, not runtime observations')
    if evidence.get('source_projects'):result['source']['projects']=evidence['source_projects']
    if model.get('artifact_scope'):
        result['artifact_scope']=model['artifact_scope']
    return result
