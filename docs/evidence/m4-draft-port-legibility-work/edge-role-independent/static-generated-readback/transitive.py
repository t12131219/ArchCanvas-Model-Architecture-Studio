"""Fresh ArchCanvas authored model; static declarations are not runtime verification."""
import torch
from torch import nn


class AuthoredModel(nn.Module):
    def __init__(self):
        super().__init__()
        self.node_ca978112ca1bbdca = nn.Identity()
        self.node_3e23e8160039594a = nn.ReLU()
        self.node_2e7d2c03a9507ae2 = nn.Identity()

    def forward(self, node_2d711642b726b044):
        node_ca978112ca1bbdca = self.node_ca978112ca1bbdca(node_2d711642b726b044)
        node_3e23e8160039594a = self.node_3e23e8160039594a(node_ca978112ca1bbdca)
        node_2e7d2c03a9507ae2 = self.node_2e7d2c03a9507ae2(node_3e23e8160039594a)
        node_09f5ffef28309853 = node_2e7d2c03a9507ae2 + node_2d711642b726b044
        return {'out': node_09f5ffef28309853}
