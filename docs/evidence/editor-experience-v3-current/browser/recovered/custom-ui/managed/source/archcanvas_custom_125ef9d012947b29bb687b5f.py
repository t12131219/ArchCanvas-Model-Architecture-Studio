from torch import nn
class PairFusion(nn.Module):
    def __init__(self, width=4, bias=False):
        super().__init__()
        self.project = nn.Linear(width, width, bias=bias)
    def forward(self, left, *, right):
        return self.project(left), right

# Stable output anchors for ArchCanvas composition; no execution occurred.
from torch import nn as _archcanvas_nn

class _ArchCanvasCustomModule(_archcanvas_nn.Module):
    def __init__(self):
        super().__init__()
        self.inner = PairFusion(width=4, bias=False)
        self.output_1 = _archcanvas_nn.Identity()
        self.output_2 = _archcanvas_nn.Identity()

    def forward(self, left, right):
        result = self.inner(left=left, right=right)
        return {'output_1': self.output_1(result[0]), 'output_2': self.output_2(result[1])}
