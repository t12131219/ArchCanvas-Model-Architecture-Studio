"""Handwritten sample contracts, independent of runtime/rebind implementations.

No user weights or source are loaded by importing this module. Test execution
must use its own /tmp project and the formal isolated worker.
"""

from __future__ import annotations

import copy


SOURCE = '''from torch import nn

class CrossAttention(nn.Module):
    def __init__(self):
        super().__init__()
        self.key_activation = nn.ReLU(inplace=False)
        self.attention = nn.MultiheadAttention(8, 2, dropout=0.2, batch_first=True)

    def forward(self, q, memory, mask):
        alternative = self.key_activation(memory)
        output, weights = self.attention(q, memory, memory, attn_mask=mask, need_weights=False)
        return output
'''


INPUT_SPEC = {
    'schemaVersion': 1,
    'inputs': {
        'q': {'shape': [2, 3, 8], 'dtype': 'float32', 'fill': 'normal'},
        'memory': {'shape': [2, 5, 8], 'dtype': 'float32', 'fill': 'normal'},
        'mask': {'shape': [3, 5], 'dtype': 'bool', 'fill': 'zeros'},
    },
    'constructor': {},
    'seed': 37,
    'modes': ['eval', 'train'],
}


EXPECTED_MODULE_KINDS = {'key_activation': 'ReLU', 'attention': 'MultiheadAttention'}
EXPECTED_PARAMETER_FACTS = {
    'attention.in_proj_weight': {'shape': [24, 8], 'dtype': 'float32'},
    'attention.in_proj_bias': {'shape': [24], 'dtype': 'float32'},
    'attention.out_proj.weight': {'shape': [8, 8], 'dtype': 'float32'},
    'attention.out_proj.bias': {'shape': [8], 'dtype': 'float32'},
}
EXPECTED_OUTPUT = {'shape': [2, 3, 8], 'dtype': 'float32'}
EXPECTED_ROLE_SHAPES = {
    'query': {'shape': [2, 3, 8], 'dtype': 'float32'},
    'key': {'shape': [2, 5, 8], 'dtype': 'float32'},
    'value': {'shape': [2, 5, 8], 'dtype': 'float32'},
    'attn_mask': {'shape': [3, 5], 'dtype': 'bool'},
}
EXPECTED_RELATIONS_BEFORE = {
    ('q', 'q', 'CrossAttention', 'q', 'data'),
    ('memory', 'memory', 'CrossAttention', 'memory', 'memory'),
    ('mask', 'mask', 'CrossAttention', 'mask', 'mask'),
    ('memory', 'memory', 'key_activation', 'input', 'data'),
    ('q', 'q', 'attention', 'query', 'data'),
    ('memory', 'memory', 'attention', 'key', 'memory'),
    ('memory', 'memory', 'attention', 'value', 'memory'),
    ('mask', 'mask', 'attention', 'attn_mask', 'mask'),
    ('attention', 'output', 'output', 'value', 'data'),
}
EXPECTED_RELATIONS_AFTER = EXPECTED_RELATIONS_BEFORE - {
    ('memory', 'memory', 'attention', 'key', 'memory'),
} | {
    ('key_activation', 'output', 'attention', 'key', 'memory'),
}


def expected_source(raw: bytes = SOURCE.encode()) -> bytes:
    old = b'self.attention(q, memory, memory, attn_mask=mask, need_weights=False)'
    new = b'self.attention(q, alternative, memory, attn_mask=mask, need_weights=False)'
    assert raw.count(old) == 1
    return raw.replace(old, new, 1)


def input_spec(**changes):
    result = copy.deepcopy(INPUT_SPEC)
    result.update(changes)
    return result
