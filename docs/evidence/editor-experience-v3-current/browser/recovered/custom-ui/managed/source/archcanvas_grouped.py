"""Fresh grouped ArchCanvas source; static graph only."""
import torch
from torch import nn
import archcanvas_custom_125ef9d012947b29bb687b5f

class AuthoredModel(nn.Module):
    def __init__(self):
        super().__init__()
        self.node_b610cc5bdee1 = archcanvas_custom_125ef9d012947b29bb687b5f._ArchCanvasCustomModule()
        self.node_78e45839ffcf = archcanvas_custom_125ef9d012947b29bb687b5f._ArchCanvasCustomModule()

    def forward(self, node_b859bb60336f62b7, node_6ca91cfa71e17d6e):
        node_b610cc5bdee1 = self.node_b610cc5bdee1(left=node_b859bb60336f62b7, right=node_6ca91cfa71e17d6e)
        node_78e45839ffcf = self.node_78e45839ffcf(left=node_b610cc5bdee1['output_1'], right=node_b610cc5bdee1['output_2'])
        return {'n_f85ad229869645128160ab60eb3edc05': node_b610cc5bdee1['output_1'], 'n_8a759663e71946f4bdf79f41fd828e5a': node_b610cc5bdee1['output_2'], 'n_1b11313095e04c2eac09446f12f2e026': node_78e45839ffcf['output_1'], 'n_71fcbad66960481fb2cb54d3138a7f7a': node_78e45839ffcf['output_2']}
