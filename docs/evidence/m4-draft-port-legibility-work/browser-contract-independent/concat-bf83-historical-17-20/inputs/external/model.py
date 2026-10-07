"""Fresh ArchCanvas authored model; static declarations are not runtime verification."""
import torch
from torch import nn


class AuthoredModel(nn.Module):
    def __init__(self):
        super().__init__()

    def forward(self, node_b2860af7f4fc5f1c, node_2bc48fab69cd26bb):
        node_829efc83bc2a5d4c = torch.cat((node_b2860af7f4fc5f1c, node_2bc48fab69cd26bb), dim=1)
        return {'n_ff375e01525344e5997678b17aa40016': node_829efc83bc2a5d4c}
