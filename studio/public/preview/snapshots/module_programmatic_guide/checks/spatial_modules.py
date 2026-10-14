"""Reproducible STN/PixelShuffle source contracts and mutation checks.

Parse the frozen caller source; never import or execute upstream model code.
Temporary evidence and deliberately changed source copies are discarded.
"""
from __future__ import annotations

import ast
import copy
import json
from pathlib import Path
import shutil
import sys
from tempfile import TemporaryDirectory

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))
import bootstrap  # noqa: E402,F401 - resolves the sibling static engine
from evidence import collect, semantic_ir  # noqa: E402
from verify import source_checks  # noqa: E402
from module_adapters import pixelshuffle, stn  # noqa: E402


def _class(tree, name):
    return next(n for n in tree.body if isinstance(n, ast.ClassDef) and n.name == name)


def _method(cls, name):
    return next(n for n in cls.body if isinstance(n, ast.FunctionDef) and n.name == name)


def _member(fn, name):
    return next(n.value for n in fn.body if isinstance(n, ast.Assign)
                and len(n.targets) == 1 and isinstance(n.targets[0], ast.Attribute)
                and n.targets[0].attr == name)


def _constant(node):
    if isinstance(node, ast.BinOp) and isinstance(node.op, ast.Mult):
        return _constant(node.left) * _constant(node.right)
    return ast.literal_eval(node)


def _kwargs(call):
    return {k.arg: _constant(k.value) for k in call.keywords if k.arg is not None}


def _nodes(ir):
    return {n['id']: n for n in ir['nodes']}


def _edge(ir, src, dst, role, sp=None, dp=None):
    return any(e['src'] == src and e['dst'] == dst and e['role'] == role
               and (sp is None or e['src_port'] == sp)
               and (dp is None or e['dst_port'] == dp) for e in ir['edges'])


def _contracts(irs):
    rows = []

    def check(key, condition, name):
        rows.append(dict(module=key, name=name, passed=bool(condition)))

    tree = ast.parse((ROOT / 'sources' / stn.SOURCE).read_text())
    cls = _class(tree, 'Net')
    init = _method(cls, '__init__')
    forward = _method(cls, 'stn')
    loc = _member(init, 'localization')
    fc = _member(init, 'fc_loc')
    ir = irs['stn']; n = _nodes(ir); p = ir['profile']
    check('stn', ast.unparse(loc.func) == 'nn.Sequential'
          and [ast.unparse(c.func) for c in loc.args] ==
          ['nn.Conv2d', 'nn.MaxPool2d', 'nn.ReLU', 'nn.Conv2d', 'nn.MaxPool2d', 'nn.ReLU'],
          'literal localization Sequential has Conv/Pool/ReLU/Conv/Pool/ReLU order')
    spatial = 28
    for index, call in enumerate(loc.args):
        identity = ['stn.loc.conv1', 'stn.loc.pool1', 'stn.loc.relu1',
                    'stn.loc.conv2', 'stn.loc.pool2', 'stn.loc.relu2'][index]
        current = n[identity]; kw = _kwargs(call)
        check('stn', current['module_identity'] == f'localization.{index}',
              f'{identity}: exact Sequential member identity')
        if index in (0, 3):
            channels_in, channels_out = [_constant(v) for v in call.args]
            kernel = kw['kernel_size']
            spatial = (spatial - kernel) // 1 + 1
            check('stn', current['in_channels'] == channels_in
                  and current['out_channels'] == channels_out
                  and current['kernel_size'] == kernel and current['stride'] == 1
                  and current['padding'] == 0 and current['bias'] is True
                  and not {'stride', 'padding', 'bias'} & kw.keys(),
                  f'{identity}: source channels/kernel and omitted Conv defaults')
            check('stn', current['parameters'] ==
                  [f'localization.{index}.weight', f'localization.{index}.bias'],
                  f'{identity}: separate learned weight and bias owner')
        elif index in (1, 4):
            kernel = _constant(call.args[0]); stride = kw['stride']
            spatial = (spatial - kernel) // stride + 1
            check('stn', current['kernel_size'] == kernel == 2
                  and current['stride'] == stride == 2,
                  f'{identity}: source Pool kernel and stride')
        else:
            check('stn', _constant(call.args[0]) is True and current['inplace'] is True,
                  f'{identity}: source positional inplace ReLU')
        channels = 8 if index < 3 else 10
        check('stn', current['shape'] == f'[B,{channels},{spatial},{spatial}]',
              f'{identity}: independently calculated spatial extent')
    check('stn', ast.unparse(fc.func) == 'nn.Sequential'
          and [ast.unparse(c.func) for c in fc.args] == ['nn.Linear', 'nn.ReLU', 'nn.Linear'],
          'literal fc_loc is Linear/ReLU/Linear')
    for index, identity in [(0, 'stn.fc1'), (2, 'stn.fc2')]:
        call = fc.args[index]
        dimensions = [_constant(v) for v in call.args]
        current = n[identity]
        check('stn', [current['in_features'], current['out_features']] == dimensions
              and current['module_identity'] == f'fc_loc.{index}'
              and current['parameters'] == [f'fc_loc.{index}.weight', f'fc_loc.{index}.bias']
              and current['bias'] is True and not call.keywords,
              f'{identity}: source dimensions, unique owner, omitted bias default')
    check('stn', spatial == 3 and n['stn.flatten']['feature_width'] == 10 * spatial * spatial == 90,
          'flatten derives90 localization features instead of784 original pixels')
    check('stn', [ast.unparse(s) for s in forward.body] == [
        'xs = self.localization(x)', 'xs = xs.view(-1, 10 * 3 * 3)',
        'theta = self.fc_loc(xs)', 'theta = theta.view(-1, 2, 3)',
        'grid = F.affine_grid(theta, x.size())', 'x = F.grid_sample(x, grid)', 'return x'],
        'entire selected stn method preserves source operands/order and returns warped x')
    initializers = [ast.unparse(s) for s in init.body if isinstance(s, ast.Expr)]
    check('stn', 'self.fc_loc[2].weight.data.zero_()' in initializers
          and 'self.fc_loc[2].bias.data.copy_(torch.tensor([1, 0, 0, 0, 1, 0], dtype=torch.float))' in initializers
          and n['stn.fc2']['initial_weight'] == 'zeros'
          and n['stn.fc2']['initial_bias'] == [1, 0, 0, 0, 1, 0],
          'source identity initialization retains learnable fc_loc.2 parameters')
    check('stn', _edge(ir, 'stn.input', 'stn.grid', 'shape_dependency', 'shape', 'size')
          and n['stn.grid']['ordered_operands'] == ['stn.theta', 'stn.input:shape'],
          'affine_grid reads theta and original image shape only')
    check('stn', _edge(ir, 'stn.input', 'stn.sample', 'retained_image', 'image', 'image')
          and n['stn.sample']['ordered_operands'] == ['stn.input', 'stn.grid']
          and _edge(ir, 'stn.grid', 'stn.sample', 'tensor'),
          'grid_sample reads retained original image pixels and generated grid')
    check('stn', all(n[i]['align_corners_argument'] == 'omitted'
                    and n[i]['opaque_runtime_boundary'] is True for i in ['stn.grid', 'stn.sample'])
          and n['stn.sample']['mode_argument'] == n['stn.sample']['padding_mode_argument'] == 'omitted',
          'caller omits sampling options; library implementations stay opaque')
    parameters = [v for node in n.values() for v in node.get('parameters', [])]
    check('stn', len(parameters) == len(set(parameters)) == 8,
          'exactly eight learned parameter tensors, excluding separate classifier members')
    check('stn', ir['artifact_scope'] == 'module' and p['classifier_excluded'] is True
          and p['model_executed'] is False
          and p['input_shape'] == p['output_shape'] == ['B', 1, 28, 28],
          'static module-only selected shape and classifier exclusion')

    tree = ast.parse((ROOT / 'sources' / pixelshuffle.SOURCE).read_text())
    cls = _class(tree, 'Net'); init = _method(cls, '__init__')
    forward = _method(cls, 'forward'); initializer = _method(cls, '_initialize_weights')
    conv = _member(init, 'conv4'); shuffle = _member(init, 'pixel_shuffle')
    ir = irs['pixelshuffle']; n = _nodes(ir); p = ir['profile']
    check('pixelshuffle', ast.unparse(conv.func) == 'nn.Conv2d'
          and ast.unparse(conv.args[1]) == 'upscale_factor ** 2'
          and [_constant(a) for i, a in enumerate(conv.args) if i != 1] ==
          [32, (3, 3), (1, 1), (1, 1)] and not conv.keywords,
          'literal Conv4 is32->r², kernel3, stride1, padding1; bias defaultTrue')
    check('pixelshuffle', ast.unparse(shuffle.func) == 'nn.PixelShuffle'
          and [ast.unparse(a) for a in shuffle.args] == ['upscale_factor'] and not shuffle.keywords,
          'one actual nn.PixelShuffle constructor using same upscale_factor')
    check('pixelshuffle', [ast.unparse(s) for s in forward.body][-3:] == [
        'x = self.relu(self.conv3(x))', 'x = self.pixel_shuffle(self.conv4(x))', 'return x'],
        'exact scope follows omitted Conv3/ReLU and ends Conv4->PixelShuffle->return')
    check('pixelshuffle', ast.unparse(initializer.body[-1]) == 'init.orthogonal_(self.conv4.weight)'
          and not any(ast.unparse(c).startswith('self.conv4.bias') for c in ast.walk(initializer)),
          'Conv4 weight orthogonally initialized; bias not explicitly reinitialized')
    conv = n['pixelshuffle.conv4']; shuffle = n['pixelshuffle.shuffle']
    r = p['upscale_factor']; channels = conv['out_channels']; h = w = 8
    out_h = (h + 2 * conv['padding'][0] - conv['kernel_size'][0]) // conv['stride'][0] + 1
    check('pixelshuffle', r == 3 and channels == r ** 2 and out_h == h
          and p['conv4_shape'] == ['B', channels, h, w]
          and p['output_shape'] == ['B', channels // (r ** 2), h * r, w * r],
          'explicit r3 profile independently yields32->9->1 channels and8->24 spatial size')
    check('pixelshuffle', conv['parameters'] == ['conv4.weight', 'conv4.bias']
          and conv['activation_after'] is False and conv['weight_initialization'] == 'orthogonal',
          'two Conv4 parameter tensors, constructor context, no post-convolution ReLU')
    check('pixelshuffle', shuffle['learnable'] is False and shuffle['parameters'] == []
          and shuffle['opaque_runtime_boundary'] is True
          and shuffle['runtime_dependency'] == 'torch.nn.PixelShuffle',
          'parameter-free single real library call remains opaque')
    offsets = [[r * i + j for j in range(r)] for i in range(r)]
    check('pixelshuffle', offsets == [[0, 1, 2], [3, 4, 5], [6, 7, 8]]
          and shuffle['standard_api_mapping'] ==
          'Y[b,c,3*h+i,3*w+j] = X[b,9*c+3*i+j,h,w]; 0<=i,j<3'
          and shuffle['mapping_provenance'] ==
          'standard PixelShuffle mathematical/API contract; not source AST operators',
          'offset equation explicitly attributed to standard API, not invented source children')
    check('pixelshuffle', _edge(ir, 'pixelshuffle.conv4', 'pixelshuffle.projection', 'boundary')
          and _edge(ir, 'pixelshuffle.projection', 'pixelshuffle.shuffle', 'tensor')
          and not any(x.get('parent') == 'pixelshuffle.shuffle' for x in n.values()),
          'projection boundary forwards Conv4 result once; no fake reshape/permute internals')
    check('pixelshuffle', ir['artifact_scope'] == 'module' and p['model_executed'] is False
          and n['pixelshuffle.input']['scope_boundary'] == 'after self.relu(self.conv3(x))',
          'module scope preserves feature-input boundary instead of claiming full model')
    return rows


def _negatives(irs, temporary_root):
    def edit(identity, field, value):
        return lambda ir: _nodes(ir)[identity].__setitem__(field, value)

    def change_size_role(ir):
        next(e for e in ir['edges'] if e['src'] == 'stn.input'
             and e['dst'] == 'stn.grid')['role'] = 'retained_image'

    def fake_child(ir):
        original = _nodes(ir)['pixelshuffle.shuffle']
        ir['nodes'].append(dict(original, id='pixelshuffle.shuffle.fake_reshape',
                                parent='pixelshuffle.shuffle', kind='tensor'))

    cases = [
        ('stn', 'sampler consumes localization feature map',
         edit('stn.sample', 'ordered_operands', ['stn.localization', 'stn.grid'])),
        ('stn', 'shape dependency incorrectly becomes image-pixel dependency', change_size_role),
        ('stn', 'invent explicit align_corners=True', edit('stn.grid', 'align_corners_argument', True)),
        ('stn', 'identity initialization loses lower diagonal',
         edit('stn.fc2', 'initial_bias', [1, 0, 0, 0, 0, 0])),
        ('stn', 'localization wrongly pads first convolution',
         edit('stn.loc.conv1', 'shape', '[B,8,28,28]')),
        ('pixelshuffle', 'profile changes r3 to r2', lambda ir: ir['profile'].__setitem__('upscale_factor', 2)),
        ('pixelshuffle', 'shuffle claims learned parameters', edit('pixelshuffle.shuffle', 'learnable', True)),
        ('pixelshuffle', 'invent postConv ReLU', edit('pixelshuffle.conv4', 'activation_after', True)),
        ('pixelshuffle', 'wrong channel-offset order', edit('pixelshuffle.shuffle', 'standard_api_mapping',
         'Y[b,c,3*h+i,3*w+j] = X[b,9*c+i+3*j,h,w]')),
        ('pixelshuffle', 'invent internal source reshape operator', fake_child),
    ]
    adapters = {'stn': stn, 'pixelshuffle': pixelshuffle}
    rows = []
    for key, name, mutate in cases:
        changed = copy.deepcopy(irs[key]); mutate(changed)
        try:
            adapters[key].validate_ir(changed)
        except (ValueError, AssertionError) as exc:
            rows.append(dict(module=key, name=name, rejected=True, reason=str(exc), kind='semantic'))
        else:
            rows.append(dict(module=key, name=name, rejected=False, kind='semantic'))
    for key, adapter, before, after in [
        ('stn', stn, 'F.affine_grid(theta, x.size())',
         'F.affine_grid(theta, x.size(), align_corners=True)'),
        ('pixelshuffle', pixelshuffle, 'nn.PixelShuffle(upscale_factor)',
         'nn.Upsample(scale_factor=upscale_factor)'),
    ]:
        slug, inner = adapter.SOURCE.split('/', 1)
        destination = temporary_root / ('changed-source-' + key)
        shutil.copytree(ROOT / 'sources' / slug, destination / slug)
        file = destination / slug / inner
        original = file.read_text()
        if before not in original:
            raise AssertionError('Mutation target missing from frozen source: ' + adapter.SOURCE)
        file.write_text(original.replace(before, after))
        try:
            collect(adapter.build(), destination, destination / 'evidence',
                    manifest_path=ROOT / 'source_manifest.json')
        except ValueError as exc:
            reason = str(exc)
            rejected = reason.startswith('Source changed; review adapter before drawing: ')
            rows.append(dict(module=key, name='changed frozen source: ' + after,
                             rejected=rejected, reason=reason, kind='frozen_source'))
        else:
            rows.append(dict(module=key, name='changed frozen source: ' + after,
                             rejected=False, kind='frozen_source'))
    return rows


def run():
    """Return a JSON-serializable report without depending on saved previews."""
    irs = {}; guards = {}; sources = {}
    with TemporaryDirectory(prefix='archcanvas-spatial-check-') as directory:
        temporary_root = Path(directory)
        for key, adapter in [('stn', stn), ('pixelshuffle', pixelshuffle)]:
            model = adapter.build(); folder = temporary_root / key
            evidence = collect(model, ROOT / 'sources', folder,
                               manifest_path=ROOT / 'source_manifest.json')
            irs[key] = semantic_ir(model, evidence)
            guards[key] = adapter.validate_ir(irs[key])
            sources[key] = source_checks(folder, evidence, irs[key],
                manifest_path=ROOT / 'source_manifest.json', source_root=ROOT / 'sources')
        contracts = _contracts(irs)
        negatives = _negatives(irs, temporary_root)
    failures = [r['module'] + ': ' + r['name'] for r in contracts if not r['passed']]
    failures += [r['module'] + ': unrejected ' + r['name'] for r in negatives if not r['rejected']]
    return dict(passed=not failures, failures=failures, upstream_code_executed=False,
                source_contract_count=len(contracts), source_contracts=contracts,
                adapter_guard_count=sum(len(v) for v in guards.values()), adapter_guards=guards,
                negative_count=len(negatives), negative_cases=negatives, source_checks=sources)


if __name__ == '__main__':
    report = run()
    print(json.dumps(report, ensure_ascii=False, indent=2))
    raise SystemExit(0 if report['passed'] else 1)
