/* A concrete first occurrence can explain a modeled structure in its original
 * sequence. Later calls stay ordered and individually recoverable. No call,
 * parameter or value is substituted by the representative's computation. */
(function(root){
  'use strict';
  const S=root.SemanticStructuralRepresentatives||(typeof require==='function'?require('./structural-representatives.js'):null);
  const copy=x=>JSON.parse(JSON.stringify(x));
  function build(ir,base){
    const checked=S.inspect(ir),nodes=base.nodes.map(copy),by=new Map(nodes.map(n=>[n.id,n])),findings=base.findings.map(copy),original=new Set(ir.nodes.map(n=>n.id));
    const children=new Map();for(const n of nodes){if(!children.has(n.parent))children.set(n.parent,[]);children.get(n.parent).push(n.id);}
    const closure=id=>{const all=[],todo=[id];for(let i=0;i<todo.length;i++){all.push(todo[i]);todo.push(...children.get(todo[i])||[]);}return all;};
    const sequences=[],diagnostics=checked.diagnostics.map(copy);
    for(const seq of checked.sequences){
      if(seq.rows.some(r=>by.get(r.instance)?.parent!==seq.id)){diagnostics.push({sequence:seq.id,reason:'concrete instance parent is not the visible sequence'});continue;}
      const groups=seq.groups.map((g,i)=>({...g,group:i})),proved=groups.filter(g=>g.status==='proved');
      if(!proved.length){diagnostics.push({sequence:seq.id,reason:'no proved local structure; keep all original boundaries'});continue;}
      const samples=new Set(proved.map(g=>g.representative)),groupOf=new Map(groups.flatMap(g=>g.instances.map(id=>[id,g]))),remainders=[];
      for(const group of proved){
        const n=by.get(group.representative);n.structure_representative={group:group.group,representative:group.representative,indices:group.indices.slice(),instances:group.instances.slice(),status:'proved'};
        n.sequence_sample={sequence:seq.id,index:n.repeat_index,scope:'one concrete source call in its original position; structure only; no value substitution'};
      }
      for(let i=0;i<seq.rows.length;){
        const row=seq.rows[i],group=groupOf.get(row.instance);
        if(samples.has(row.instance)||row.status!=='proved'){i++;continue;}
        let end=i+1;while(end<seq.rows.length&&!samples.has(seq.rows[end].instance)&&seq.rows[end].status==='proved'&&groupOf.get(seq.rows[end].instance)===group)end++;
        const rows=seq.rows.slice(i,end);i=end;if(rows.length<2)continue;
        const members=rows.map(r=>r.instance),id='paper:serial-remainder:'+members[0];if(by.has(id))throw Error('duplicate sequence presentation ID');
        const canonical=members.flatMap(closure).filter(id=>original.has(id)),inside=new Set(canonical),positions=rows.map(r=>r.index+1);
        const suffix={id,parent:seq.id,kind:'composite',semantic_type:'serial-remainder',presentation_only:true,evidence_status:'static-only',runtime_evidence:[],
          label:rows.length+' subsequent source calls',source:members.flatMap(id=>by.get(id).source||[]).slice(0,32),canonical_members:canonical,
          boundary_ports:ir.edges.filter(e=>inside.has(e.source)!==inside.has(e.target)).map(copy),finding:id,
          region_summary:'Positions '+positions[0]+'–'+positions.at(-1)+' · separate instances',
          sequence_remainder:{sequence:seq.id,instances:members,indices:rows.map(r=>r.index),structure_group:group.group,representative:group.representative,
            parameter_sharing:by.get(seq.id).repeat_contract.parameter_sharing,scope:'ordered concrete source calls; internal calls and every canonical cut retained; no output equality'}};
        nodes.push(suffix);by.set(id,suffix);children.set(id,members);for(const member of members)by.get(member).parent=id;
        children.set(seq.id,(children.get(seq.id)||[]).filter(id=>!members.includes(id)).concat(id));
        findings.push({id,rule:'ordered-source-call-suffix',presentation:'group',evidence_scope:'presentation',members,
          roles:{sequence:seq.id,positions,representative:group.representative},proof:['Freshly reconstructed local structure agrees with the source certificate. Only a contiguous run is folded. Original source order, individual identities, operands and exact boundary cuts remain. No numerical equality, purity or parameter stability is asserted.']});
        remainders.push({node:id,instances:members,indices:rows.map(r=>r.index)});
      }
      const record={sequence:seq.id,samples:proved.map(g=>({instance:g.representative,index:seq.rows.find(r=>r.instance===g.representative).index,group:g.group,source_positions:g.indices.map(i=>i+1)})),remainders,
        unclassified:seq.rows.filter(r=>r.status!=='proved').map(r=>({instance:r.instance,index:r.index,reason:r.reason})),scope:'concrete calls in source order; representatives describe local structure only'};
      by.get(seq.id).sequence_frontier=record;sequences.push(record);
    }
    return {...base,nodes,findings,publication:{...base.publication,inline_sequences:{schema:'ordered-sequence-frontier/1',sequences,diagnostics}}};
  }
  const api={build};root.SemanticSequenceFrontier=api;if(typeof module!=='undefined')module.exports=api;
})(typeof window!=='undefined'?window:globalThis);
