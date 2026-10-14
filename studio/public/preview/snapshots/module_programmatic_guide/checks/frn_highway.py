"""Independent frozen AST contracts and critical operand/identity negatives."""
import ast,copy,importlib,json,sys,tempfile
from pathlib import Path
HERE=Path(__file__).resolve().parents[1]
if str(HERE) not in sys.path:sys.path.insert(0,str(HERE))
import bootstrap
from evidence import collect,semantic_ir,symbols_in

def run():
    records=[];negative=[]
    def check(condition,name):
        if not condition:raise AssertionError(name)
        records.append(name)
    frn_path=HERE/'sources/rasbt-modules/pytorch_ipynb/cnn/nin-cifar10_filter-response-norm.py'
    source=frn_path.read_text();t=ast.parse(source)
    c=next(x for x in t.body if isinstance(x,ast.ClassDef) and x.name=='FilterResponseNormalization')
    funcs={x.name:x for x in c.body if isinstance(x,ast.FunctionDef)}
    init=ast.unparse(funcs['__init__']);fwd=ast.unparse(funcs['forward'])
    check("torch.mean(x.pow(2), (2, 3), keepdims=True)" in fwd,'FRN AST H/W uncentered second moment')
    check('x * torch.rsqrt(nu2 + torch.abs(self.eps))' in fwd,'FRN AST original x and abs eps normalization')
    check('return torch.max(self.gamma * x + self.beta, self.tau)' in fwd,'FRN AST two-tensor learned threshold')
    check(init.count('torch.empty([1, num_features, 1, 1]).normal_()')==3 and 'self.eps = torch.Tensor([eps])' in init
          and 'register_buffer' not in init,'FRN AST three normal_ Parameters and plain epsilon')
    check(sum(isinstance(x,ast.ClassDef) and x.name=='NiN' for x in t.body)==2,'FRN Notebook actual NiN redefinition')
    symbols_in(source,str(frn_path),required={'FilterResponseNormalization','FilterResponseNormalization.forward'})
    try:symbols_in(source,str(frn_path),required={'NiN'})
    except ValueError as error:negative.append(dict(case='ambiguous NiN binding',rejected=True,reason=str(error)))
    else:raise AssertionError('Duplicate referenced NiN accepted')
    hw=ast.parse((HERE/'sources/pytorch-highway/highway/highway.py').read_text())
    h=next(x for x in hw.body if isinstance(x,ast.ClassDef) and x.name=='Highway');hfunc={x.name:x for x in h.body if isinstance(x,ast.FunctionDef)}
    hi=ast.unparse(hfunc['__init__']);hf=ast.unparse(hfunc['forward'])
    check(hi.count('nn.ModuleList([nn.Linear(size, size) for _ in range(num_layers)])')==3,'Highway AST three separately constructed ModuleLists')
    check('self.f = f' in hi and 'linear = self.linear[layer](x)' in hf,'Highway AST supplied f and learned carry')
    check('gate = F.sigmoid(self.gate[layer](x))' in hf and 'x = gate * nonlinear + (1 - gate) * linear' in hf,'Highway AST complementary same gate products and update')
    check('for layer in range(self.num_layers):' in hf,'Highway AST sequential depth loop')
    for key in ['frn_tlu','highway']:
        adapter=importlib.import_module('module_adapters.'+key);model=adapter.build()
        with tempfile.TemporaryDirectory(prefix='module-contract-') as tmp:
            evidence=collect(model,HERE/'sources',Path(tmp),manifest_path=HERE/'source_manifest.json')
            ir=semantic_ir(model,evidence)
        guards=adapter.validate_ir(ir)
        def node_change(identity,field,value):
            return lambda x:next(n for n in x['nodes'] if n['id']==identity).__setitem__(field,value)
        def reroute(src,dst,newsrc):
            return lambda x:next(e for e in x['edges'] if e['src']==src and e['dst']==dst).__setitem__('src',newsrc)
        mutations=[
          ('wrong FRN reduction axes',node_change('frn.mean','dims',[0,2,3])),
          ('squared x used as retained input',reroute('frn.norm','frn.scale','frn.square')),
          ('tau wired into beta Add',reroute('frn.beta','frn.beta_add','frn.tau')),
          ('epsilon incorrectly registered buffer',node_change('frn.epsilon','registered_buffer',True)),
          ('TLU incorrectly reduced maximum',node_change('frn.threshold','reduction',True)),
        ] if key=='frn_tlu' else [
          ('identity carry replaces learned value',reroute('highway.layer0.carry_linear','highway.layer0.carry_product','highway.input')),
          ('complement from wrong source',reroute('highway.layer0.sigmoid','highway.layer0.complement','highway.layer0.relu')),
          ('depth weights wrongly shared',node_change('highway.layer1.carry_linear','parameter','linear.0')),
          ('layer1 uses original input',reroute('highway.layer0.add','highway.layer1.gate','highway.input')),
        ]
        for name,mutation in mutations:
            broken=copy.deepcopy(ir);mutation(broken)
            try:adapter.validate_ir(broken)
            except (ValueError,AssertionError) as error:negative.append(dict(module=key,case=name,rejected=True,reason=str(error)))
            else:raise AssertionError('Accepted semantic error: '+name)
        records.append(dict(module=key,positive_ir_checks=guards))
    return dict(passed=True,source_contracts=records,negative_cases=negative,model_executed=False)
if __name__=='__main__':print(json.dumps(run(),ensure_ascii=False,indent=2))
