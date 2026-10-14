#!/usr/bin/env python3
"""Independent, read-only source/IR/visible-terminal review of 25 model examples.

This intentionally does not call layout.validate or adapter.validate_ir. The
geometric checks alone cannot detect a tensor wire attached to the wrong scope.
It reads JSON/SVG evidence only; no upstream PyTorch model or notebook executes.
"""
from __future__ import annotations
import argparse
import hashlib
import json
from pathlib import Path

HERE = Path(__file__).resolve().parent
PROTOTYPE = HERE.parents[1]
CURRENT = PROTOTYPE / 'model_zoo_programmatic_guide'
KEYS = ['lenet', 'resnet', 'densenet', 'unet', 'vae', 'lstm', 'alexnet',
        'mobilenetv2', 'nin', 'textcnn', 'convae', 'dcgan', 'vgg16', 'resnet50',
        'convvae', 'ccvae', 'gru', 'bilstm', 'mobilenetv3', 'resnet101', 'vgg19',
        'convgan', 'dcwgan', 'graphnet', 'lstmcell']
VIEWS = ['overview', 'modules', 'detailed']


def read(path):
    return json.loads(path.read_text())


def source_quote(relative, expression):
    path = CURRENT / 'sources' / relative
    lines = path.read_text().splitlines()
    matches = [dict(line=i, text=line.strip()) for i, line in enumerate(lines, 1)
               if expression in line]
    if not matches:
        raise AssertionError(f'source expression not found: {path}: {expression}')
    return dict(path=str(path), expression=expression, matches=matches,
                sha256=hashlib.sha256(path.read_bytes()).hexdigest())


def visible(identity, nodes, boxes):
    while identity not in boxes:
        identity = nodes[identity].get('parent')
        if identity is None:
            raise AssertionError('No visible ancestor')
    return identity


def terminal(route, side):
    value = route.get(side)
    return value.split(':', 1)[0] if isinstance(value, str) else None


def sem(route, side):
    if route.get('semantic_' + side):
        return route['semantic_' + side]
    binding = route.get('operand_binding')
    if binding:
        return binding['producer' if side == 'src' else 'child']
    return terminal(route, side)


def audit(guide):
    models = {}
    for key in KEYS:
        folder = guide / 'generated' / key
        ir = read(folder / 'semantic_ir.json')
        evidence = read(folder / 'source_evidence.json')
        nodes = {node['id']: node for node in ir['nodes']}
        models[key] = dict(ir=ir, nodes=nodes, evidence=evidence, views={})
        for view in VIEWS:
            layout = read(folder / f'layout_{view}.json')
            boxes = {box['id']: box for box in layout['boxes']}
            models[key]['views'][view] = dict(layout=layout, boxes=boxes)

    checks, candidates = [], []

    def check(category, key, view, condition, description, **details):
        checks.append(dict(category=category, model=key, view=view,
                           status='pass' if condition else 'fail',
                           description=description, **details))

    # Exhaustive inventory precedes the focused source assertions.
    for key, model in models.items():
        for view, record in model['views'].items():
            boxes, layout = record['boxes'], record['layout']
            check('inventory', key, view,
                  all(box['id'] in model['nodes'] and box['source']
                      and all(s in model['evidence']['symbols'] for s in box['source'])
                      for box in boxes.values()),
                  'Every visible glyph binds to a saved source symbol')
            check('terminal_inventory', key, view,
                  all(terminal(route, side) is None or terminal(route, side) in boxes
                      for route in layout['routes'] for side in ('src', 'dst')),
                  'Every claimed physical endpoint is a visible glyph')
            for route in layout['routes']:
                if 'semantic_src' not in route:
                    continue
                ends = {side: terminal(route, side) for side in ('src', 'dst')}
                if any(boxes[node]['expanded'] for node in ends.values() if node):
                    candidates.append(dict(model=key, view=view, route=route,
                                           review='Expanded boundary requires source interface projection'))

    def endpoint_case(key, view, semantic_source, semantic_target,
                      actual_source, actual_target, source):
        record, nodes = models[key]['views'][view], models[key]['nodes']
        expected = dict(src=visible(actual_source, nodes, record['boxes']),
                        dst=visible(actual_target, nodes, record['boxes']))
        routes = [route for route in record['layout']['routes']
                  if sem(route, 'src') == semantic_source and sem(route, 'dst') == semantic_target]
        matches = [route for route in routes
                   if terminal(route, 'src') == expected['src']
                   and terminal(route, 'dst') == expected['dst']]
        check('source_terminal_contract', key, view, bool(matches),
              'Route reaches the source producer and consumer at the visible frontier',
              binding=[semantic_source, semantic_target], expected=expected,
              observed=routes, source=source)

    for view in VIEWS:
        for stage in range(1, 5):
            unet_source = source_quote('brain-segmentation-pytorch/unet.py',
                                       f'torch.cat((dec{stage}, enc{stage}), dim=1)')
            endpoint_case('unet', view, f'unet_enc{stage}', f'unet_dec{stage}_cat',
                          f'unet_enc{stage}_block_relu2', f'unet_dec{stage}_cat', unet_source)

    alex_source = source_quote(
        'deeplearning-models-batch2/pytorch_ipynb/cnn/cnn-alexnet-cifar10-grouped.py',
        'probas = F.softmax(logits, dim=1)')
    graph_source = source_quote(
        'deeplearning-models-batch4/pytorch_ipynb/gnn/gnn-basic-1.py',
        "self.register_buffer('A', A)")
    for view in VIEWS:
        endpoint_case('alexnet', view, 'alex.classifier', 'alex.unused_softmax',
                      'alex.fc3', 'alex.unused_softmax', alex_source)
        endpoint_case('graphnet', view, 'graphnet.adjacency', 'graphnet.expand',
                      'graphnet.buffer', 'graphnet.expand', graph_source)

    for key, name in [('convgan', 'gan-conv.py'), ('dcwgan', 'dc-wgan-1.py')]:
        source = source_quote(f'deeplearning-models-batch4/pytorch_ipynb/gan/{name}',
                              'generated_features.view(targets.size(0), 1, 28, 28)')
        for view in VIEWS:
            for a, b, start, finish in [
                    ('noise', 'generator', 'noise', 'generator.linear'),
                    ('real_input', 'real_prepare', 'real_input', 'normalize'),
                    ('generator.tanh', 'g_score_path', 'generator.tanh', 'g_image_view'),
                    ('generator.tanh', 'fake_score_path', 'generator.tanh', 'fake_image_view'),
                    ('real_flatten', 'real_score_path', 'real_flatten', 'real_image_view')]:
                endpoint_case(key, view, key + '.' + a, key + '.' + b,
                              key + '.' + start, key + '.' + finish, source)

    for key, path in [('vae', 'deeplearning-models/pytorch_ipynb/autoencoder/ae-var.py'),
                      ('convvae', 'deeplearning-models-batch3/pytorch_ipynb/autoencoder/ae-conv-var.py'),
                      ('ccvae', 'deeplearning-models-batch3/pytorch_ipynb/autoencoder/ae-cnn-cvae.py')]:
        source = source_quote(path, 'self.reparameterize(z_mean, z_log_var)')
        mean_leaf = 'mean_operand' if key == 'vae' else 'retain_mu'
        endpoint_case(key, 'detailed', key + '.mu', key + '.' + mean_leaf,
                      key + '.mu', key + '.' + mean_leaf, source)
        endpoint_case(key, 'detailed', key + '.logvar', key + '.scaled_noise',
                      key + '.logvar', key + '.half_logvar', source)
        scopes = [node for node in models[key]['nodes'].values()
                  if node['id'] in (key + '.posterior', key + '.sample_args',
                                    key + '.sample_operands')]
        check('source_argument_semantics', key, 'all',
              all(node.get('semantic_mode') == 'operand_bundle'
                  and node.get('literal_tuple') is False for node in scopes),
              'Two function arguments are independently bound, without an invented source tuple',
              source=source, observed=[dict(id=node['id'], mode=node.get('mode'),
                                          semantic_mode=node.get('semantic_mode'),
                                          dispatch=node.get('dispatch')) for node in scopes])
        epsilon_source = source_quote(path, 'torch.randn(z_mu.size(0), z_mu.size(1))')
        check('source_shape_dependency', key, 'all',
              any(edge['src'] == key + '.mu' and edge['dst'] == key + '.epsilon'
                  and edge['role'] == 'shape_dependency'
                  for edge in models[key]['ir']['edges']),
              'Gaussian sample size comes from mu shape, not its feature values', source=epsilon_source)

    residual_source = source_quote(
        'deeplearning-models/pytorch_ipynb/cnn/cnn-resnet18-mnist.py', 'out += residual')
    for stage in (2, 3, 4):
        node = models['resnet']['nodes'][f'resnet.stage{stage}.downsample.paths']
        check('source_argument_semantics', 'resnet', 'all',
              node.get('semantic_mode') == 'operand_bundle' and node.get('literal_tuple') is False,
              'Main and projected shortcut are two Add operands, without an invented tuple',
              source=residual_source, observed=dict(id=node['id'], mode=node.get('mode'),
                                                    semantic_mode=node.get('semantic_mode')))

    for key in ('resnet', 'resnet50', 'resnet101', 'mobilenetv2', 'mobilenetv3'):
        for view in VIEWS:
            routes = [route for route in models[key]['views'][view]['layout']['routes']
                      if route['role'] in ('residual', 'retained_input')]
            # The hidden state after a block must not replace the block's saved
            # input x when an expanded residual/gating bypass is projected.
            check('retained_input_identity', key, view,
                  all(route.get('semantic_src_port',
                                (route.get('src') or '').split(':', 1)[-1]) == 'in'
                      for route in routes),
                  'Residual/gate bypass retains the input port, not the transformed output',
                  observed=routes)

    cell_source = source_quote('pytorch-lstmcell-v2.5.1/benchmarks/fastrnns/custom_lstms.py',
                               'cy = (forgetgate * cx) + (ingate * cellgate)')
    for view in VIEWS:
        routes = models['lstmcell']['views'][view]['layout']['routes']
        for step in (0, 1):
            h = next((r for r in routes if sem(r, 'src') == f'lstmcell.step{step}.hy'
                      and sem(r, 'dst') == f'lstmcell.step{step+1}.hx'), None)
            c = next((r for r in routes if sem(r, 'src') == f'lstmcell.step{step}.cy'
                      and sem(r, 'dst') == f'lstmcell.step{step+1}.cx'), None)
            check('distinct_recurrent_fields', 'lstmcell', view,
                  h is not None and c is not None
                  and h['points'][0] != c['points'][0]
                  and h['points'][-1] != c['points'][-1],
                  'Hidden and cell state retain distinct terminals through folded neighboring cells',
                  source=cell_source, observed=[h, c])

    failures = [entry for entry in checks if entry['status'] == 'fail']
    return dict(schema='independent-modelzoo-arrow-audit/1', guide=str(guide.resolve()),
                model_count=len(models), view_count=len(models) * len(VIEWS),
                upstream_executed=False, geometric_validation_used=False,
                assertion_count=len(checks), passed=len(checks) - len(failures),
                failed=len(failures), expanded_endpoint_candidates=candidates,
                failures=failures, checks=checks,
                limits='Focused independent semantic contracts plus exhaustive endpoint inventory; '
                       'does not claim arbitrary model inference or runtime tensor observations.')


if __name__ == '__main__':
    parser = argparse.ArgumentParser()
    parser.add_argument('--guide', type=Path, default=CURRENT)
    parser.add_argument('--output', type=Path, default=HERE / 'endpoint_audit.json')
    args = parser.parse_args()
    result = audit(args.guide)
    args.output.parent.mkdir(parents=True, exist_ok=True)
    args.output.write_text(json.dumps(result, ensure_ascii=False, indent=2) + '\n')
    print(json.dumps({k: result[k] for k in ('model_count', 'view_count', 'assertion_count',
                                            'passed', 'failed')}, ensure_ascii=False))
