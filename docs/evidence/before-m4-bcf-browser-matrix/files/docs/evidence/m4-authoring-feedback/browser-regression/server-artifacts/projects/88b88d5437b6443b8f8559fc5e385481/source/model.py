"""Fresh ArchCanvas authored model; static declarations are not runtime verification."""
import torch
from torch import nn


class AuthoredModel(nn.Module):
    def __init__(self):
        super().__init__()
        self.node_aa44720b4d2c3683 = nn.Linear(in_features=16, out_features=32, bias=True, dtype=torch.float32)
        self.node_e0b0d5c046da4d7e = nn.Linear(in_features=32, out_features=8, bias=True, dtype=torch.float32)

    def forward(self, node_38541989d3526c4c):
        node_aa44720b4d2c3683 = self.node_aa44720b4d2c3683(node_38541989d3526c4c)
        node_e0b0d5c046da4d7e = self.node_e0b0d5c046da4d7e(node_aa44720b4d2c3683)
        return {'n_2854f13081c148f79652b0873b781151': node_e0b0d5c046da4d7e}
