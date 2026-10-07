import { edgeDashPattern } from '../../../../../studio/src/core/edgePresentation.ts';
const sparse = Array(2) as number[];
try {
  const result=edgeDashPattern({dashed:true,dashPattern:sparse});
  console.log(JSON.stringify({rejected:false,length:result.length,result,svgAttribute:result.join(' ')}));
  process.exitCode=1;
} catch (error) { console.log(JSON.stringify({rejected:true,message:String(error)})); }
