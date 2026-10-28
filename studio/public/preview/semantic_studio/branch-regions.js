/* Source-independent fork/join decomposition. These are dependency regions,
 * with no assertion of concurrency, tensor equivalence or model identity. */
(function(root){
  'use strict';
  function discover(ids,adj,{maxBranches=64,maxPath=64,maxMembers=96}={}){
    const present=new Set(ids),pred=new Map(ids.map(id=>[id,new Set()])),order=new Map(ids.map((id,i)=>[id,i]));
    const next=id=>[...(adj.get(id)||[])].filter(to=>present.has(to));
    for(const id of ids)for(const to of next(id))pred.get(to).add(id);
    const results=[];
    for(const entry of ids){
      const starts=next(entry);if(starts.length<2||starts.length>maxBranches)continue;
      const branches=[];let exit=null,valid=true;
      for(const start of starts){
        const path=[],seen=new Set([entry]);let at=start;
        while(pred.get(at).size===1&&path.length<maxPath){
          if(seen.has(at)){valid=false;break;}seen.add(at);path.push(at);
          const following=next(at);if(following.length!==1){valid=false;break;}at=following[0];
        }
        if(!valid||!path.length||seen.has(at)||pred.get(at).size<2||exit!==null&&exit!==at){valid=false;break;}
        exit=at;branches.push(path);
      }
      if(!valid)continue;
      const members=branches.flat();
      // All incoming/outgoing dependency boundaries of an interior path must
      // be the same fork and join. Side exits, bypasses and shared interiors
      // invalidate the decomposition instead of silently becoming a chain.
      if(members.length<3||members.length>maxMembers||new Set(members).size!==members.length)continue;
      const tails=new Set(branches.map(path=>path.at(-1)));
      if(pred.get(exit).size!==tails.size||[...pred.get(exit)].some(id=>!tails.has(id)))continue;
      results.push({entry,exit,branches,members});
    }
    return results.sort((a,b)=>a.members.length-b.members.length||order.get(a.entry)-order.get(b.entry));
  }
  const api={discover};root.SemanticBranchRegions=api;if(typeof module!=='undefined')module.exports=api;
})(typeof window!=='undefined'?window:globalThis);
