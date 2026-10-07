"""Fresh ArchCanvas authored model; static declarations are not runtime verification."""
import torch
from torch import nn


class AuthoredModel(nn.Module):
    def __init__(self):
        super().__init__()

    def forward(self, node_1a042a60af4d18eb, node_48b7467abe7a11c2):
        node_db4236e645ba7fe7 = node_1a042a60af4d18eb + node_48b7467abe7a11c2
        node_11b4ac995ce51f03 = torch.cat((node_db4236e645ba7fe7, node_1a042a60af4d18eb), dim=1)
        return {'n_05049c883315494a904ffe410c52dde8': node_11b4ac995ce51f03}
