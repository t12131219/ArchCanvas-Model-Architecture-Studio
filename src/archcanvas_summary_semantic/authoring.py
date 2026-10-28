"""Static source-to-module compilation for the local authoring workspace.

Submitted source is parsed, never imported or executed. Each result carries its
source text and extraction limitations; a graph edit is not execution evidence.
"""
import ast
import hashlib
import json
import tempfile
from pathlib import Path
from .analyzer import analyze
from .schema import validate_ir, seal


def compile_module(source, entry, constructor=None):
    if not isinstance(source, str) or len(source.encode()) > 120_000:
        raise ValueError('源码不能为空且不能超过 120KB')
    tree = ast.parse(source, filename='custom_module.py')
    if not isinstance(entry, str) or not entry.isidentifier():
        raise ValueError('请填写模块类名或函数名')
    if not any(isinstance(n, (ast.ClassDef, ast.FunctionDef)) and n.name == entry for n in tree.body):
        raise ValueError('源码中没有此入口定义')
    constructor = constructor or {}
    if not isinstance(constructor, dict):
        raise ValueError('构造参数必须是 JSON 对象')
    with tempfile.TemporaryDirectory(prefix='archcanvas-authoring-') as directory:
        path = Path(directory) / 'custom_module.py'
        path.write_text(source, encoding='utf-8')
        ir = analyze(path, entry, constructor, max_nodes=5000, max_depth=12)
        check = validate_ir(ir)
        if not check['ok']:
            raise ValueError('; '.join(check['errors'][:8]))
    virtual='authoring://module/'+hashlib.sha256(source.encode()).hexdigest()+'/custom_module.py'
    ir=json.loads(json.dumps(ir,ensure_ascii=False).replace(str(path),virtual))
    # Source locations and construction references now use a stable, portable
    # URI backed by the source text saved in this module document.
    from .identity import certify as identities
    from .symbolic_values import certify as values
    from .structure import certify as structures
    from .contracts import recognize_contracts
    identities(ir['nodes'],ir['edges']);values(ir['nodes'],ir['edges']);structures(ir['nodes'],ir['edges'])
    recognize_contracts(ir);seal(ir)
    check=validate_ir(ir)
    if not check['ok']:raise ValueError('; '.join(check['errors'][:8]))
    # File is deliberately ephemeral. Source text travels with the module, so
    # the user never depends on a temporary host path for recovering a mapping.
    return {'schema': 'semantic-module/1', 'title': entry, 'source': source,
            'entry': entry, 'constructor': constructor, 'ir': ir,
            'analysis': {'executed': False, 'validation': check,
                         'opaque': sum(n['kind'] == 'opaque' for n in ir['nodes'])}}


def preset_definitions():
    header = 'import torch\nfrom torch import nn\n\n'
    def module(name, init, forward, args='x', params=None, level='module'):
        source = header + f'class {name}(nn.Module):\n    def __init__(self' + (', ' + ', '.join(f'{k}={repr(v)}' for k,v in (params or {}).items()) if params else '') + '):\n        super().__init__()\n'
        source += ''.join('        '+line+'\n' for line in init.splitlines())
        source += f'    def forward(self, {args}):\n' + ''.join('        '+line+'\n' for line in forward.splitlines())
        return {'key':name,'title':name,'source':source,'entry':name,'constructor':params or {},'level':level}
    definitions = [
        module('Linear','self.proj = nn.Linear(in_features, out_features, bias=bias)','return self.proj(x)',params={'in_features':64,'out_features':64,'bias':True}),
        module('Attention','self.width = width\nself.q = nn.Linear(width, width)\nself.k = nn.Linear(width, width)\nself.v = nn.Linear(width, width)',
               'q = self.q(x)\nk = self.k(context)\nv = self.v(context)\nreturn attention_core(q, k, v)',args='x, context',params={'width':64}),
        module('Add','pass','return x + skip',args='x, skip'),
        module('Conv2d','self.conv = nn.Conv2d(in_channels, out_channels, kernel_size, padding=padding)','return self.conv(x)',params={'in_channels':3,'out_channels':16,'kernel_size':3,'padding':1}),
        module('CNN','self.conv = nn.Conv2d(in_channels, out_channels, kernel_size, padding=1)\nself.act = nn.ReLU()\nself.pool = nn.MaxPool2d(2)','return self.pool(self.act(self.conv(x)))',params={'in_channels':3,'out_channels':16,'kernel_size':3}),
        module('FeedForward','self.first = nn.Linear(width, hidden)\nself.act = nn.ReLU()\nself.last = nn.Linear(hidden, width)','return self.last(self.act(self.first(x)))',params={'width':64,'hidden':256}),
        module('Residual','self.proj = nn.Linear(width, width)\nself.norm = nn.LayerNorm(width)','return self.norm(x + self.proj(x))',params={'width':64}),
        module('LayerNorm','self.norm = nn.LayerNorm(width, eps=eps)','return self.norm(x)',params={'width':64,'eps':1e-5}),
        module('Embedding','self.embedding = nn.Embedding(vocab_size, width)','return self.embedding(x)',params={'vocab_size':1000,'width':64}),
        module('GRU','self.cell = nn.GRUCell(input_size, hidden_size)','return self.cell(x, hidden)',args='x, hidden',params={'input_size':64,'hidden_size':64}),
        module('Concat','self.dim = dim','return torch.cat((x, y), dim=self.dim)',args='x, y',params={'dim':-1}),
        module('MatMul','pass','return torch.matmul(x, y)',args='x, y',level='atomic'),
        module('ReLU','pass','return torch.relu(x)',level='atomic'),
        module('Softmax','self.dim = dim','return torch.softmax(x, dim=self.dim)',params={'dim':-1},level='atomic'),
        module('Transpose','self.axis0 = axis0\nself.axis1 = axis1','return x.transpose(self.axis0, self.axis1)',params={'axis0':-2,'axis1':-1},level='atomic'),
        module('Multiply','pass','return x * y',args='x, y',level='atomic'),
    ]
    helper='import math\n\ndef attention_core(q, k, v):\n    scores = torch.matmul(q, k.transpose(-2, -1)) / math.sqrt(q.size(-1))\n    weights = torch.softmax(scores, dim=-1)\n    return torch.matmul(weights, v)\n\n'
    for definition in definitions:
        if definition['key']=='Attention':definition['source']=definition['source'].replace('class Attention',helper+'class Attention',1)
    return definitions


def certify_assembly(ir):
    """Recompute local structural contracts over declared draft facts.

    This checks operand structure, not equivalence to an original Python file
    or executable compatibility of the assembled model.
    """
    from .contracts import recognize_contracts
    from .schema import seal
    if not isinstance(ir, dict) or not ir.get('authoring', {}).get('edited'):
        raise ValueError('需要显式用户编辑的组合图')
    nodes=ir.get('nodes',[]);edges=ir.get('edges',[])
    if len(nodes)>16000 or len(edges)>50000:raise ValueError('超过编辑图规模限制')
    ids={n['id'] for n in nodes}
    if len(ids)!=len(nodes) or any(e['source'] not in ids or e['target'] not in ids for e in edges):raise ValueError('图身份或端点无效')
    ir['semantic_contracts']=[]
    ir.pop('semantic_contract_basis',None)
    recognize_contracts(ir)
    for c in ir.get('semantic_contracts',[]):
        c['scope']='local operand structure of the declared user assembly; not equivalence to original source or execution coverage'
        c['not_asserted']=[*c.get('not_asserted',[]),'assembled-program execution','shape compatibility','unchanged original source']
    ir['authoring']['local_contracts_recomputed']=True
    return seal(ir)
