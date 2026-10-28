import fs from 'node:fs';
import path from 'node:path';
import {fileURLToPath} from 'node:url';
import ts from 'typescript';

/** Conservative graph: include type imports and literal URL/Worker entries too. */
export function auditPreviewAuthorities(studioRoot: string) {
  const root=path.resolve(studioRoot),base=path.join(root,'src');
  const files=fs.readdirSync(base,{recursive:true}).map(String).filter(n=>/\.(ts|tsx)$/.test(n)).map(n=>path.join(base,n));
  const all=new Set(files),edges=new Map<string,string[]>();
  const unresolved: {file:string;expression:string}[]=[],retiredDeclarations:{file:string;name:string}[]=[];
  const retiredNames=new Set(['prepareMovePreview','previewMoveScene','planLayoutRecovery']);
  const rel=(file:string)=>path.relative(root,file).split(path.sep).join('/');
  for(const file of files){
    const ast=ts.createSourceFile(file,fs.readFileSync(file,'utf8'),ts.ScriptTarget.Latest,true),imports:string[]=[];
    function visit(node:ts.Node){
      let spec:string|undefined;
      if((ts.isImportDeclaration(node)||ts.isExportDeclaration(node))&&node.moduleSpecifier&&ts.isStringLiteral(node.moduleSpecifier))spec=node.moduleSpecifier.text;
      if(ts.isImportTypeNode(node)&&ts.isLiteralTypeNode(node.argument)&&ts.isStringLiteral(node.argument.literal))spec=node.argument.literal.text;
      if(ts.isCallExpression(node)&&node.expression.kind===ts.SyntaxKind.ImportKeyword){
        if(node.arguments.length===1&&ts.isStringLiteral(node.arguments[0]))spec=node.arguments[0].text;
        else unresolved.push({file:rel(file),expression:node.getText(ast)});
      }
      if(ts.isNewExpression(node)&&ts.isIdentifier(node.expression)&&node.expression.text==='URL'&&node.arguments?.[0]&&ts.isStringLiteral(node.arguments[0]))spec=node.arguments[0].text;
      if(spec?.startsWith('.')){
        const target=path.resolve(path.dirname(file),spec),resolved=[target,target+'.ts',target+'.tsx',path.join(target,'index.ts')].find(value=>all.has(value));
        if(resolved)imports.push(resolved);
      }
      if((ts.isFunctionDeclaration(node)||ts.isVariableDeclaration(node))&&node.name&&ts.isIdentifier(node.name)&&retiredNames.has(node.name.text))retiredDeclarations.push({file:rel(file),name:node.name.text});
      ts.forEachChild(node,visit);
    }
    visit(ast);edges.set(file,[...new Set(imports)]);
  }
  const reachable=new Set<string>();
  function walk(file:string){if(reachable.has(file))return;reachable.add(file);for(const child of edges.get(file)||[])walk(child);}
  const entry=path.join(base,'main.tsx');if(all.has(entry))walk(entry);
  const retiredPaths=['src/core/movePreview.ts','src/core/layoutRecovery.ts'];
  const existingRetiredPaths=retiredPaths.filter(file=>fs.existsSync(path.join(root,file)));
  const testOnlyImports=files.flatMap(file=>{
    const ast=ts.createSourceFile(file,fs.readFileSync(file,'utf8'),ts.ScriptTarget.Latest,true),found:{file:string;specifier:string}[]=[];
    function visit(node:ts.Node){
      if(ts.isStringLiteral(node)&&(/retired-preview/.test(node.text)||node.text.startsWith('../tests/')||node.text.includes('/tests/')))found.push({file:rel(file),specifier:node.text});
      ts.forEachChild(node,visit);
    }visit(ast);return found;
  });
  return {ok:all.has(entry)&&!unresolved.length&&!existingRetiredPaths.length&&!retiredDeclarations.length&&!testOnlyImports.length,
    scope:'Studio source imports, exports, literal dynamic imports and URL/Worker entries, including type dependencies; not a whole-product feature or performance certificate',
    entry:'src/main.tsx',modules:files.length,reachableModules:reachable.size,
    reachable:[...reachable].map(rel).sort(),unreachable:files.filter(file=>!reachable.has(file)).map(rel).sort(),
    unresolvedDynamicImports:unresolved,existingRetiredPaths,retiredDeclarations,testOnlyImports,
    sourceEdges:[...edges].map(([from,to])=>({from:rel(from),to:to.map(rel)}))};
}

if(process.argv[1]&&path.resolve(process.argv[1])===fileURLToPath(import.meta.url)){
  const args=process.argv.slice(2),rootAt=args.indexOf('--studio'),outputAt=args.indexOf('--output');
  const report=auditPreviewAuthorities(rootAt>=0?args[rootAt+1]:fileURLToPath(new URL('../',import.meta.url)));
  const content=JSON.stringify(report,null,2)+'\n';
  if(outputAt>=0)fs.writeFileSync(args[outputAt+1],content);else process.stdout.write(content);
  if(!report.ok)process.exitCode=1;
}
