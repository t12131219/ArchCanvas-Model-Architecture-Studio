"""Frozen AST formula contracts + module operand/identity counterexamples."""
import sys,ast,json,copy,tempfile
from pathlib import Path
HERE=Path(__file__).resolve().parents[1];sys.path.insert(0,str(HERE))
import bootstrap
from evidence import symbols_in,collect,semantic_ir
from module_adapters.root_definitions import CASES
from module_adapters.root_support import build_case,validate_case

FROZEN=json.loads((HERE/'checks/root_ast_contracts.json').read_text())

def ast_contract(c,text):
 symbols=symbols_in(text,c['source'],set(c['symbols']))
 for name,expr in c['expressions']:
  expected=ast.dump(ast.parse(expr,mode='eval').body,include_attributes=False)
  if not any(ast.dump(node,include_attributes=False)==expected for node in ast.walk(symbols[name])):
   raise ValueError('source contract changed: '+name+' / '+expr)
 return True

def run():
 manifest=json.loads((HERE/'source_manifest.json').read_text())
 for slug,p in json.loads((HERE/'staging/root_source_manifest.json').read_text()).items():
  if slug not in manifest:manifest[slug]=p
 negatives=[];reports={}
 with tempfile.TemporaryDirectory(prefix='root-module-contracts-') as tmp:
  tmp=Path(tmp);mp=tmp/'manifest.json';mp.write_text(json.dumps(manifest))
  for key,c in CASES.items():
   contract=FROZEN[key]
   source=(HERE/'sources'/contract['source']).read_text();ast_contract(contract,source)
   model=build_case(key);out=tmp/key;out.mkdir();evidence=collect(model,HERE/'sources',out,manifest_path=mp)
   ir=semantic_ir(model,evidence);labels=validate_case(key,ir)
   def expect_bad(name,mutator):
    bad=copy.deepcopy(ir);mutator(bad)
    try:validate_case(key,bad)
    except (AssertionError,ValueError,KeyError):rejected=True
    else:rejected=False
    negatives.append(dict(module=key,case=name,rejected=rejected));assert rejected,(key,name)
   edge=c['edges'][-1];a,b=edge[:2]
   expect_bad('omit required output dependency',lambda x:x['edges'].__setitem__(slice(None),[e for e in x['edges'] if not(e['src']==key+'.'+a and e['dst']==key+'.'+b)]))
   if len(c['inputs'])>1:
    chosen=next(e for e in c['edges'] if e[0]==c['inputs'][1]['id']);a,b=chosen[:2]
    expect_bad('disconnect independent operand/state',lambda x:x['edges'].__setitem__(slice(None),[e for e in x['edges'] if not(e['src']==key+'.'+a and e['dst']==key+'.'+b)]))
   actual=next((n for s in c['stages'] for n in s['ops'] if 'expression' in n),None)
   if actual:
    expect_bad('replace real source formula',lambda x:next(n for n in x['nodes'] if n['id']==key+'.'+actual['id']).__setitem__('expression','textbook_substitute(x)'))
   parameter_node=next((n for n in c['inputs']+[n for stage in c['stages'] for n in stage['ops']] if n.get('parameters') or n.get('buffers')),None)
   if parameter_node:
    field='parameters' if parameter_node.get('parameters') else 'buffers'
    expect_bad('change parameter or buffer identity',lambda x:next(n for n in x['nodes'] if n['id']==key+'.'+parameter_node['id']).__setitem__(field,['invented_state']))
   pname=next(iter(c['profile']))
   expect_bad('select unsupported runtime/profile',lambda x:x['profile'].__setitem__(pname,'unreviewed'))
   # Replace exactly a required AST expression by a distinct Call, then check
   # the independent source contract, without executing either expression.
   symbol,expr=contract['expressions'][0];wanted=ast.dump(ast.parse(expr,mode='eval').body,include_attributes=False)
   tree=ast.parse(source)
   class Replace(ast.NodeTransformer):
    def visit(self,node):
     if ast.dump(node,include_attributes=False)==wanted:
      return ast.copy_location(ast.parse('unreviewed_formula()',mode='eval').body,node)
     return super().visit(node)
   mutated=ast.unparse(Replace().visit(tree))
   try:ast_contract(contract,mutated)
   except ValueError:rejected=True
   else:rejected=False
   negatives.append(dict(module=key,case='alter frozen AST formula',rejected=rejected));assert rejected,key
   reports[key]=dict(passed=True,source_contract_count=len(c['contracts']),semantic_check_count=len(labels))
 return dict(passed=True,modules=reports,negative_cases=negatives,source_executed=False,
  scope='Reviewed generative/flow/ordinal profiles; contracts do not prove arbitrary other profiles.')
if __name__=='__main__':
 result=run();print(json.dumps(result,ensure_ascii=False,indent=2))
