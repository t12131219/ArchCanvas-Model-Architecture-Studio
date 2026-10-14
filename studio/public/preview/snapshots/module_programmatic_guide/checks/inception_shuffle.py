"""Independent frozen-source AST contracts and 17 adversarial IR checks.

Does not import or execute upstream PyTorch code, render figures, or depend on
previous previews. Temporary evidence copies exist only during run().
"""
from __future__ import annotations

import ast
import copy
import hashlib
import importlib
import json
from pathlib import Path
import sys
import tempfile

HERE = Path(__file__).resolve().parents[1]
if str(HERE) not in sys.path:
    sys.path.insert(0, str(HERE))
import bootstrap  # noqa: E402; bind the reviewed sibling static engine
from evidence import collect, semantic_ir  # noqa: E402
from verify import source_checks  # noqa: E402


def source_contract(key, source_text):
    tree=ast.parse(source_text)
    if key=='inception_a':
        classes={n.name:n for n in tree.body if isinstance(n,ast.ClassDef)}
        m={n.name:n for n in classes['InceptionA'].body if isinstance(n,ast.FunctionDef)}
        init=m['__init__']; expected=['branch1x1','branch5x5_1','branch5x5_2','branch3x3dbl_1','branch3x3dbl_2','branch3x3dbl_3','branch_pool']
        assigns=[n for n in init.body if isinstance(n,ast.Assign) and isinstance(n.targets[0],ast.Attribute)]
        assert [n.targets[0].attr for n in assigns]==expected
        kernels=[[kw.value.value for kw in n.value.keywords if kw.arg=='kernel_size'][0] for n in assigns]
        assert kernels==[1,1,5,1,3,3,1]
        widths=[n.value.args[1].value if isinstance(n.value.args[1],ast.Constant) else n.value.args[1].id for n in assigns]
        assert widths==[64,48,64,64,96,96,'pool_features']
        outputs=next(n.value for n in m['_forward'].body if isinstance(n,ast.Assign) and any(isinstance(t,ast.Name) and t.id=='outputs' for t in n.targets))
        assert isinstance(outputs,ast.List) and [n.id for n in outputs.elts]==['branch1x1','branch5x5','branch3x3dbl','branch_pool']
        returned=m['forward'].body[-1].value
        assert isinstance(returned,ast.Call) and ast.unparse(returned.func)=='torch.cat' and returned.args[1].value==1
        bmethods={n.name:n for n in classes['BasicConv2d'].body if isinstance(n,ast.FunctionDef)}
        calls=[n.value for n in bmethods['__init__'].body if isinstance(n,ast.Assign)]
        assert ast.unparse(calls[0].func)=='nn.Conv2d' and next(k.value.value for k in calls[0].keywords if k.arg=='bias') is False
        assert ast.unparse(calls[1].func)=='nn.BatchNorm2d' and next(k.value.value for k in calls[1].keywords if k.arg=='eps')==.001
        bf=bmethods['forward'].body
        assert [ast.unparse(n.value.func) for n in bf]==['self.conv','self.bn','F.relu']
        assert next(k.value.value for k in bf[-1].value.keywords if k.arg=='inplace') is True
        return ['AST attributes and seven exact kernels/channels','AST literal output list/order and cat dim1','AST BasicConv Conv/no-bias -> BN/eps.001 -> inplace ReLU']
    function=next(n for n in tree.body if isinstance(n,ast.FunctionDef) and n.name=='channel_shuffle')
    transforms=[n.value for n in function.body if isinstance(n,ast.Assign) and len(n.targets)==1 and isinstance(n.targets[0],ast.Name) and n.targets[0].id=='x']
    assert len(transforms)==3
    assert ast.unparse(transforms[0].func)=='x.view' and [ast.unparse(n) for n in transforms[0].args]==['batchsize','groups','channels_per_group','height','width']
    swapped=transforms[1]
    assert isinstance(swapped.func,ast.Attribute) and swapped.func.attr=='contiguous' and not swapped.args
    transpose=swapped.func.value
    assert ast.unparse(transpose.func)=='torch.transpose' and [ast.unparse(n) for n in transpose.args]==['x','1','2']
    assert ast.unparse(transforms[2].func)=='x.view' and [ast.unparse(n) for n in transforms[2].args]==['batchsize','-1','height','width']
    assert isinstance(function.body[-1],ast.Return) and function.body[-1].value.id=='x'
    return ['AST first view named axes','AST transpose(1,2).contiguous() exact composition','AST final view -1 and direct return']

def mutate_node(ir, identity, field, value):
    next(n for n in ir['nodes'] if n['id']==identity)[field]=value

def negative_tests(key,adapter,ir):
    if key=='inception_a':
        mutations=[
            ('Concat changed to Add',lambda d:mutate_node(d,'inca.concat','kind','add')),
            ('Wrong concat axis',lambda d:mutate_node(d,'inca.concat','dim',2)),
            ('Wrong literal list order',lambda d:mutate_node(d,'inca.branches','branch_order',list(reversed(next(n for n in d['nodes'] if n['id']=='inca.branches')['branch_order'])))),
            ('AvgPool changed to MaxPool',lambda d:mutate_node(d,'inca.avgpool','pool_type','max')),
            ('5x5 replaced by3x3',lambda d:mutate_node(d,'inca.branch5x5_2.conv','kernel_size',3)),
            ('BN eps changed',lambda d:mutate_node(d,'inca.branch1x1.bn','eps',1e-5)),
            ('Distinct branch parameter conflated',lambda d:mutate_node(d,'inca.branch3x3dbl_1.conv','parameter','branch1x1.conv')),
            ('Output changed to288 channels',lambda d:mutate_node(d,'inca.concat','shape','[B,288,35,35]')),
            ('Same-input fork removed',lambda d:d['edges'].__setitem__(slice(None),[e for e in d['edges'] if not(e['src']=='inca.branches' and e['dst']=='inca.path_pool' and e['role']=='fork')])),
        ]
    else:
        mutations=[
            ('Contiguous deleted',lambda d:d['nodes'].__setitem__(slice(None),[n for n in d['nodes'] if n['id']!='shuffle.contiguous'])),
            ('Wrong transpose axes',lambda d:mutate_node(d,'shuffle.transpose','dims',[2,3])),
            ('groups changed to12',lambda d:d['profile'].__setitem__('groups',12)),
            ('Swapped shape left unchanged',lambda d:mutate_node(d,'shuffle.transpose','shape','[B,2,12,8,8]')),
            ('Final inferred channel count changed',lambda d:mutate_node(d,'shuffle.flatten_view','inferred_channels',12)),
            ('Identity permutation supplied',lambda d:d['profile'].__setitem__('permutation_output_to_input',list(range(24)))),
            ('Learned parameter invented',lambda d:mutate_node(d,'shuffle.group_view','parameter','invented.weight')),
            ('Contiguous bypassed',lambda d:d['edges'].__setitem__(slice(None),[e for e in d['edges'] if not(e['src']=='shuffle.transpose' and e['dst']=='shuffle.contiguous')])),
        ]
    result=[]
    for label,mutation in mutations:
        wrong=copy.deepcopy(ir);mutation(wrong)
        try:adapter.validate_ir(wrong)
        except (ValueError,KeyError) as exc:result.append(dict(case=label,rejected=True,error=str(exc)))
        else:result.append(dict(case=label,rejected=False))
    return result


def run():
    """Return a portable JSON-serializable report; never write generated/ files."""
    reports = []
    with tempfile.TemporaryDirectory(prefix="archcanvas-inception-shuffle-") as scratch:
        for key in ["inception_a", "channel_shuffle"]:
            adapter = importlib.import_module("module_adapters." + key)
            result = dict(module=key, passed=False, model_executed=False)
            try:
                model = adapter.build()
                folder = Path(scratch) / key
                folder.mkdir()
                evidence = collect(model, HERE / "sources", folder,
                                   manifest_path=HERE / "source_manifest.json")
                ir = semantic_ir(model, evidence)
                result["source_integrity"] = source_checks(
                    folder, evidence, ir, manifest_path=HERE / "source_manifest.json",
                    source_root=HERE / "sources")
                source_text = (HERE / "sources" / adapter.SOURCE).read_text()
                result["source_contract"] = source_contract(key, source_text)
                result["semantic_checks"] = adapter.validate_ir(ir)
                result["negative_cases"] = negative_tests(key, adapter, ir)
                result["source_sha256"] = hashlib.sha256(source_text.encode()).hexdigest()
                result["adapter_sha256"] = hashlib.sha256(Path(adapter.__file__).read_bytes()).hexdigest()
                result["passed"] = all(case["rejected"] for case in result["negative_cases"])
            except Exception as exc:
                result["error"] = type(exc).__name__ + ": " + str(exc)
            reports.append(result)
    return dict(schema="module-inception-shuffle-checks/1",
                passed=all(report["passed"] for report in reports),
                source_executed=False, modules=reports,
                negative_case_count=sum(len(report.get("negative_cases", [])) for report in reports))


if __name__ == "__main__":
    print(json.dumps(run(), ensure_ascii=False, indent=2))
