"""Fresh ArchCanvas authored model; static declarations are not runtime verification."""
import torch
from torch import nn


class AuthoredModel(nn.Module):
    def __init__(self):
        super().__init__()
        self.node_6f0c87624e7b0bf4 = nn.Conv2d(in_channels=3, out_channels=8, kernel_size=[3, 3], stride=[1, 1], padding=[1, 1], dilation=[1, 1], groups=1, bias=True, dtype=torch.float32)
        self.node_86c7ca30e08cf4dd = nn.ReLU()
        self.node_713601f419c08b23 = nn.MaxPool2d(kernel_size=[2, 2], stride=[2, 2], padding=[0, 0], dilation=[1, 1], ceil_mode=False)
        self.node_f13844467264b413 = nn.AdaptiveAvgPool2d(output_size=[1, 1])
        self.node_e64a0d83673df36f = nn.Flatten(start_dim=1, end_dim=-1)
        self.node_8ab65981d7be221c = nn.Linear(in_features=8, out_features=4, bias=True, dtype=torch.float32)

    def forward(self, node_381cd6d6785c1932):
        node_6f0c87624e7b0bf4 = self.node_6f0c87624e7b0bf4(node_381cd6d6785c1932)
        node_86c7ca30e08cf4dd = self.node_86c7ca30e08cf4dd(node_6f0c87624e7b0bf4)
        node_713601f419c08b23 = self.node_713601f419c08b23(node_86c7ca30e08cf4dd)
        node_f13844467264b413 = self.node_f13844467264b413(node_713601f419c08b23)
        node_e64a0d83673df36f = self.node_e64a0d83673df36f(node_f13844467264b413)
        node_8ab65981d7be221c = self.node_8ab65981d7be221c(node_e64a0d83673df36f)
        return {'n_a367f92d56b9408f94959c87a9b73d29': node_8ab65981d7be221c}
