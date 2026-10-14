"""Resolve source-backed interfaces to the visible frontier, never from graph ranks.

port_bindings declare aliases, not new computations. A list represents separate
operands/consumers; it must never be rendered as an invented common tensor bus.
"""
from __future__ import annotations


class EndpointResolver:
    def __init__(self, ir, visible):
        self.ir=ir; self.nodes={n['id']:n for n in ir['nodes']}
        self.parents={n['id']:n['parent'] for n in ir['nodes']}
        self.visible=set(visible)
        self.children={n:[] for n in self.nodes}
        for n in ir['nodes']:
            if n['parent'] in self.children:self.children[n['parent']].append(n['id'])
        self.edges=ir['edges']

    def expanded(self,node):
        return node in self.visible and any(c in self.visible for c in self.children[node])

    def aliases(self,node,port,direction):
        n=self.nodes[node]; binding=n.get('port_bindings',{}).get(port)
        if binding is not None:
            targets=[dict(x) for x in (binding if isinstance(binding,list) else [binding]) if x.get('direction',direction)==direction]
            if targets:return targets
        if direction=='src':
            found=[dict(node=e['src'],port=e['src_port']) for e in self.edges
                   if e['dst']==node and e['dst_port']==port and (e['role'] in ('tuple_collection','operand_collection') or e['role']=='boundary' and port=='out')]
        else:
            found=[dict(node=e['dst'],port=e['dst_port']) for e in self.edges
                   if e['src']==node and e['src_port']==port and port=='in' and (e['role']=='boundary' or e['role']=='shape_dependency' and n.get('mode')=='chain' and n.get('input_role',n.get('boundary_input_role'))=='shape')]
        # A shape is metadata of the actual output producer, not of an
        # arbitrary last child selected by visual position.
        if not found and direction=='src' and port=='shape':
            found=[dict(x,port='shape') for x in self.aliases(node,'out','src')]
        if not found and port=='out' and direction=='src' and n.get('mode')=='parallel':
            collection=sorted((e for e in self.edges if e['dst']==node and e['role'] in ('tuple_collection','operand_collection')),
                              key=lambda e:int(e['dst_port'].split('[',1)[1].rstrip(']')))
            found=[dict(node=e['src'],port=e['src_port'],operand=i) for i,e in enumerate(collection)]
        return found

    def incoming(self,node,port):
        return [e for e in self.edges if e['dst']==node and e['dst_port']==port
                and e['role'] not in ('tuple_collection','operand_collection')]

    def full_targets(self,node,port,direction,seen=()):
        key=(node,port,direction)
        if key in seen:raise ValueError('Cyclic endpoint alias: '+repr(key))
        aliases=self.aliases(node,port,direction)
        if not aliases:return [(node,port)]
        return [p for a in aliases for p in self.full_targets(a['node'],a.get('port','out' if direction=='src' else 'in'),direction,seen+(key,))]

    def project(self,node,port,direction):
        visible=node
        while visible not in self.visible:
            visible=self.parents.get(visible)
            if visible is None:raise ValueError('No visible endpoint ancestor: '+node)
        if visible==node:return dict(node=node,port=port,projection='exact')
        # Recover an exported field if the folded interface declares it.
        candidates=[]
        for name in self.nodes[visible].get('port_bindings',{}):
            if (node,port) in self.full_targets(visible,name,direction):candidates.append(name)
        if 'out' in candidates and len(candidates)>1:candidates.remove('out')
        if 'in' in candidates and len(candidates)>1:candidates.remove('in')
        if len(candidates)==1:field=candidates[0]
        elif direction=='src' and (node,port) in self.full_targets(visible,'out','src'):field='out' if len(self.full_targets(visible,'out','src'))==1 else node+':'+port
        elif direction=='dst' and (node,port) in self.full_targets(visible,'in','dst'):field='in'
        else:field=node+':'+port
        return dict(node=visible,port=field,projection='folded',canonical_node=node,canonical_port=port)

    def resolve(self,node,port,direction,seen=()):
        key=(node,port,direction)
        if key in seen:raise ValueError('Cyclic visible endpoint binding: '+repr(key))
        # Captured input (residual/retained value) is the value before the
        # first operation. Trace the unique incoming producer, not its output.
        if direction=='src' and port=='in':
            incoming=self.incoming(node,'in')
            if len(incoming)==1:
                e=incoming[0]
                return [dict(t,via=[dict(node=node,port=port,rule='captured-input')]+t.get('via',[]))
                        for t in self.resolve(e['src'],e['src_port'],'src',seen+(key,))]
        if not self.expanded(node):
            if node in self.visible and not self.children[node] and direction=='src' and node in self.nodes and self.nodes[node].get('port_bindings',{}).get(port):
                aliases=self.aliases(node,port,direction)
                if aliases:return [dict(t,via=[dict(node=node,port=port,rule='returned-field')]+t.get('via',[])) for a in aliases for t in self.resolve(a['node'],a.get('port','out'),direction,seen+(key,))]
            return [self.project(node,port,direction)]
        aliases=self.aliases(node,port,direction)
        if aliases:
            result=[]
            for i,a in enumerate(aliases):
                for t in self.resolve(a['node'],a.get('port','out' if direction=='src' else 'in'),direction,seen+(key,)):
                    result.append(dict(t,via=[dict(node=node,port=port,rule='declared-interface' if port in self.nodes[node].get('port_bindings',{}) else 'IR-boundary')]+t.get('via',[]),**({'operand':i} if len(aliases)>1 else {})))
            return result
        return [dict(node=node,port=port,projection='exposed-interface')]

    def edge_endpoints(self,edge):
        src_port=edge['src_port'];dst_port=edge['dst_port']
        dst_node=self.nodes[edge['dst']]
        # A real API tuple selection reads that field, not the whole output.
        if src_port=='out' and dst_port=='in' and dst_node.get('input_selector'):
            src_port=dst_node['input_selector']
        if edge['role']=='dispatch' and self.expanded(edge['src']):
            incoming=self.incoming(edge['src'],'in')
            if len(incoming)!=1:raise ValueError('Dispatch requires a declared input tuple: '+edge['id'])
            upstream=incoming[0]
            sources=self.resolve(upstream['src'],src_port,'src')
        else:sources=self.resolve(edge['src'],src_port,'src')
        destinations=self.resolve(edge['dst'],dst_port,'dst')
        pairs=[]
        for i,s in enumerate(sources):
            for j,d in enumerate(destinations):
                if s['node']==d['node'] and (s.get('projection')=='folded' or d.get('projection')=='folded'):continue
                if s['node']==d['node'] and s['port']==d['port']:continue
                target=dict(d)
                if len(sources)>1 and len(destinations)==1 and target['port']=='in':target['port']=f'operand[{i}]'
                pairs.append((s,target))
        return pairs

    def suppress(self,edge):
        # Interface aliases are realized by resolving real edges. Drawing
        # them again leaves redundant arrowheads on empty container borders.
        if edge['role'] in ('boundary','tuple_collection','operand_collection'):return 'interface alias'
        dst=self.nodes[edge['dst']]
        if edge['role'] in ('tensor','seasonal') and self.expanded(edge['dst']) and dst.get('mode')=='parallel':
            return 'expanded operands have individual source bindings'
        destinations=self.resolve(edge['dst'],edge['dst_port'],'dst')
        if destinations and all(self.expanded(t['node']) and self.nodes[t['node']].get('mode')=='parallel' for t in destinations):
            return 'expanded operand/fork scope is supplied by individual producer edges'
        return None


def validate_contracts(ir):
    nodes={n['id']:n for n in ir['nodes']}
    resolver=EndpointResolver(ir,nodes)
    for node in nodes.values():
        for port,raw in node.get('port_bindings',{}).items():
            targets=raw if isinstance(raw,list) else [raw]
            if not targets:raise ValueError('Empty interface: '+node['id']+':'+port)
            for target in targets:
                if target['node'] not in nodes:raise ValueError('Unknown interface target: '+target['node'])
                parent=target['node']
                while parent is not None and parent!=node['id']:parent=nodes[parent]['parent']
                if parent is None:
                    local=target['node']
                    while local is not None and local!=node['parent']:local=nodes[local]['parent']
                    if target.get('direction')!='src' or local is None:raise ValueError('Interface points outside its source scope: '+node['id']+':'+port)
            for direction in ('src','dst'):resolver.full_targets(node['id'],port,direction)
