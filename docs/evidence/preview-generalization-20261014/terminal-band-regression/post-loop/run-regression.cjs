const fs=require('node:fs'),path=require('node:path'),os=require('node:os'),crypto=require('node:crypto'),{spawnSync}=require('node:child_process');
const project=path.resolve(__dirname,'../../../../..'),receipt=JSON.parse(fs.readFileSync(path.join(__dirname,'runtime-tests-receipt.json')));
const baseline=process.argv.includes('--baseline'),matrix=process.argv.includes('--matrix'),temporary=fs.mkdtempSync(path.join(os.tmpdir(),'archcanvas-terminal-post-loop-'));
const output=matrix?path.resolve(process.argv.includes('--output')?process.argv[process.argv.indexOf('--output')+1]:path.join(temporary,'matrix')):null;
const preview=path.join(temporary,'public/preview'),runtime=matrix?path.join(output,'runtime'):path.join(preview,'yworks_edge_router_lab'),tests=path.join(temporary,'tests');
fs.mkdirSync(runtime,{recursive:true});fs.mkdirSync(tests,{recursive:true});fs.writeFileSync(path.join(temporary,'package.json'),'{"type":"module"}\n');
try{
  for(const name of Object.keys(receipt.baseRuntimeFiles)){
    const filename=baseline||name!=='recursive-graph.js'?path.join(project,receipt.baseRuntimeFiles[name]):path.join(__dirname,receipt.variantOverlay),bytes=fs.readFileSync(filename);
    const actual=crypto.createHash('sha256').update(bytes).digest('hex'),expected=(baseline?receipt.baseRuntimeHashes:receipt.variantRuntimeHashes)[name];
    if(actual!==expected)throw Error('Frozen runtime hash differs: '+name);fs.writeFileSync(path.join(runtime,name),bytes);
  }
  let args;
  if(matrix){
    const mixed=process.argv.includes('--mixed');
    args=[path.join(project,'studio/scripts/check-preview-frontiers.cjs'),'--runtime-dir',runtime,'--output',output,'--phase',mixed?'mixed':'standard','--cases',mixed?'b4e7f02ce4dce8d4':'5acb264f160778bf,384ef15495a3cd00','--concurrency','1','--timeout-ms','180000'];
  }else{
    for(const name of fs.readdirSync(path.join(project,'studio/public/preview')))if(name!=='yworks_edge_router_lab')
      fs.symlinkSync(path.join(project,'studio/public/preview',name),path.join(preview,name));
    const names=baseline?['previewCleanupOrder.test.ts']:Object.keys(receipt.tests.testHashes);
    for(const name of names){const bytes=fs.readFileSync(path.join(__dirname,name));if(crypto.createHash('sha256').update(bytes).digest('hex')!==receipt.tests.testHashes[name])throw Error('Test hash differs: '+name);fs.writeFileSync(path.join(tests,name),bytes);}
    args=['--experimental-strip-types','--test','--test-isolation=none',...names.map(name=>'tests/'+name)];
  }
  const result=spawnSync(process.execPath,args,{cwd:temporary,stdio:'inherit',env:{...process.env,ARCHCANVAS_PREVIEW_TEST_RUNTIME:runtime}});process.exitCode=result.status??1;
}finally{fs.rmSync(temporary,{recursive:true,force:true});}
