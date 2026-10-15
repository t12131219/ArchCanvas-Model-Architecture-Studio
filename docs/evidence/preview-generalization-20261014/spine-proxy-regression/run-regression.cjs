const fs=require('node:fs'),path=require('node:path'),os=require('node:os'),crypto=require('node:crypto'),{spawnSync}=require('node:child_process');
const project=path.resolve(__dirname,'../../../..'),receipt=JSON.parse(fs.readFileSync(path.join(__dirname,'runtime-receipt.json')));
const baseline=process.argv.includes('--baseline'),matrix=process.argv.includes('--matrix'),temporary=fs.mkdtempSync(path.join(os.tmpdir(),'archcanvas-spine-proxy-regression-'));
const matrixOutput=matrix?path.resolve(process.argv.includes('--output')?process.argv[process.argv.indexOf('--output')+1]:path.join(temporary,'matrix')):null;
const runtime=matrix?path.join(matrixOutput,'runtime'):path.join(temporary,'public/preview/yworks_edge_router_lab'),tests=path.join(temporary,'tests');
fs.mkdirSync(runtime,{recursive:true});fs.mkdirSync(tests);fs.writeFileSync(path.join(temporary,'package.json'),'{"type":"module"}\n');
try{
  for(const name of Object.keys(receipt.baseRuntimeFiles)){
    const filename=baseline||name!=='recursive-graph.js'?path.join(project,receipt.baseRuntimeFiles[name]):path.join(__dirname,receipt.variantOverlay),bytes=fs.readFileSync(filename);
    const actual=crypto.createHash('sha256').update(bytes).digest('hex'),expected=(baseline?receipt.baseRuntimeHashes:receipt.variantRuntimeHashes)[name];
    if(actual!==expected)throw Error('Frozen runtime hash differs: '+name);fs.writeFileSync(path.join(runtime,name),bytes);
  }
  let args;
  if(matrix){
    args=[path.join(project,'studio/scripts/check-preview-frontiers.cjs'),'--runtime-dir',runtime,'--output',matrixOutput,'--phase','mixed','--cases','28c0565ef37d1aff,87dbdc94e0f6462f','--concurrency','1','--timeout-ms','180000'];
  }else{
    for(const name of ['previewRecursiveSpine.test.ts','previewWireContacts.test.ts'])fs.copyFileSync(path.join(__dirname,name),path.join(tests,name));
    args=['--experimental-strip-types','--test','--test-isolation=none',...(baseline?['--test-name-pattern','a container input proxy']:[]),'tests/previewRecursiveSpine.test.ts',...(!baseline?['tests/previewWireContacts.test.ts']:[])];
  }
  const result=spawnSync(process.execPath,args,{cwd:temporary,stdio:'inherit'});process.exitCode=result.status??1;
}finally{fs.rmSync(temporary,{recursive:true,force:true});}
