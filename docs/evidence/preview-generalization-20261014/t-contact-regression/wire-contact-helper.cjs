// Geometry only. Callers exclude equal source wire identities and licensed
// complete shared presentations before invoking this edge-pair helper.
function wireContacts(first, second, epsilon = 1e-5) {
  const distance = (a, b) => Math.hypot(a.x-b.x, a.y-b.y);
  const atTerminal = (point, route) => distance(point, route[0]) <= epsilon || distance(point, route.at(-1)) <= epsilon;
  const bins = new Map(), contacts = [];
  function add(point, strict) {
    const bx=Math.floor(point.x/epsilon),by=Math.floor(point.y/epsilon);let known;
    for(let x=bx-1;x<=bx+1&&!known;x++)for(let y=by-1;y<=by+1&&!known;y++)
      known=(bins.get(x+':'+y)||[]).find(entry=>distance(entry.point,point)<=epsilon);
    if(known){known.strict ||= strict;return;}
    const entry={point,strict};contacts.push(entry);const key=bx+':'+by,bin=bins.get(key)||[];bin.push(entry);bins.set(key,bin);
  }
  for(let i=1;i<first.length;i++)for(let j=1;j<second.length;j++){
    const a=first[i-1],b=first[i],c=second[j-1],d=second[j],ux=b.x-a.x,uy=b.y-a.y,vx=d.x-c.x,vy=d.y-c.y;
    const lengthA=Math.hypot(ux,uy),lengthB=Math.hypot(vx,vy);if(lengthA<=epsilon||lengthB<=epsilon)continue;
    const determinant=ux*vy-uy*vx;
    if(Math.abs(determinant)<=epsilon*Math.max(1,lengthA,lengthB)){
      // Positive shared runs are already rejected by the overlap validator.
      // Two collinear segments can still meet at an internal single point.
      const lineDistance=Math.abs((c.x-a.x)*uy-(c.y-a.y)*ux)/lengthA;
      if(lineDistance>epsilon)continue;
      const along=p=>((p.x-a.x)*ux+(p.y-a.y)*uy)/lengthA;
      const cAlong=along(c),dAlong=along(d),low=Math.max(0,Math.min(cAlong,dAlong)),high=Math.min(lengthA,Math.max(cAlong,dAlong));
      if(high<low-epsilon||high-low>epsilon)continue;
      const position=Math.max(0,Math.min(lengthA,(low+high)/2)),point={x:a.x+ux*position/lengthA,y:a.y+uy*position/lengthA};
      if(!atTerminal(point,first)||!atTerminal(point,second))add(point,false);
      continue;
    }
    const wx=c.x-a.x,wy=c.y-a.y,t=(wx*vy-wy*vx)/determinant,u=(wx*uy-wy*ux)/determinant;
    if(t < -epsilon/lengthA||t > 1+epsilon/lengthA||u < -epsilon/lengthB||u > 1+epsilon/lengthB)continue;
    const point={x:(a.x+Math.max(0,Math.min(1,t))*ux+c.x+Math.max(0,Math.min(1,u))*vx)/2,
      y:(a.y+Math.max(0,Math.min(1,t))*uy+c.y+Math.max(0,Math.min(1,u))*vy)/2};
    // Coincident actual route terminals are separately governed by port and
    // source contracts. Internal bends count even if both segments end here.
    if(atTerminal(point,first)&&atTerminal(point,second))continue;
    add(point,t>epsilon/lengthA&&t<1-epsilon/lengthA&&u>epsilon/lengthB&&u<1-epsilon/lengthB);
  }
  return contacts.map(({point,strict})=>({point,kind:strict?'crossing':'touch'}));
}
module.exports={wireContacts};
