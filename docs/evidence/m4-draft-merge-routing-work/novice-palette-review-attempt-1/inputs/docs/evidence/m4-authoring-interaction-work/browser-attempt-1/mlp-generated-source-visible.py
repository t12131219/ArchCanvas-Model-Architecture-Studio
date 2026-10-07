"""Fresh ArchCanvas authored model; static declarations are not runtime verification."""
import torch
from torch import nn


class AuthoredModel(nn.Module):
    def __init__(self):
        super().__init__()
        self.node_56f6b6bdc18d1fb8 = nn.Linear(in_features=16, out_features=32, bias=True, dtype=torch.float32)
        self.node_234d11cd32867e99 = nn.ReLU()
        self.node_a74e879361781eec = nn.Linear(in_features=32, out_features=4, bias=True, dtype=torch.float32)

    def forward(self, node_b93ac8ac79175f7d):
        node_56f6b6bdc18d1fb8 = self.node_56f6b6bdc18d1fb8(node_b93ac8ac79175f7d)
        node_234d11cd32867e99 = self.node_234d11cd32867e99(node_56f6b6bdc18d1fb8)
        node_a74e879361781eec = self.node_a74e879361781eec(node_234d11cd32867e99)
        return {'n_4ffa08ae12a546d4b17410a10aa0187e': node_a74e879361781eec}
