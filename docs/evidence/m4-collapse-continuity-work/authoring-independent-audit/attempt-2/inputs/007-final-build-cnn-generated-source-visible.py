"""Fresh ArchCanvas authored model; static declarations are not runtime verification."""
import torch
from torch import nn


class AuthoredModel(nn.Module):
    def __init__(self):
        super().__init__()
        self.node_0a4eabb1f9762095 = nn.Conv2d(in_channels=3, out_channels=8, kernel_size=[3, 3], stride=[1, 1], padding=[1, 1], dilation=[1, 1], groups=1, bias=True, dtype=torch.float32)
        self.node_bd66b0b5b72c4743 = nn.ReLU()
        self.node_2eb784a2b7d8e2ad = nn.MaxPool2d(kernel_size=[2, 2], stride=[2, 2], padding=[0, 0], dilation=[1, 1], ceil_mode=False)
        self.node_843566ee3a2b531b = nn.AdaptiveAvgPool2d(output_size=[1, 1])
        self.node_ba1402c048c7d3eb = nn.Flatten(start_dim=1, end_dim=-1)
        self.node_aadb373283133490 = nn.Linear(in_features=8, out_features=4, bias=True, dtype=torch.float32)

    def forward(self, node_6a6961f385e1244b):
        node_0a4eabb1f9762095 = self.node_0a4eabb1f9762095(node_6a6961f385e1244b)
        node_bd66b0b5b72c4743 = self.node_bd66b0b5b72c4743(node_0a4eabb1f9762095)
        node_2eb784a2b7d8e2ad = self.node_2eb784a2b7d8e2ad(node_bd66b0b5b72c4743)
        node_843566ee3a2b531b = self.node_843566ee3a2b531b(node_2eb784a2b7d8e2ad)
        node_ba1402c048c7d3eb = self.node_ba1402c048c7d3eb(node_843566ee3a2b531b)
        node_aadb373283133490 = self.node_aadb373283133490(node_ba1402c048c7d3eb)
        return {'n_e96ec41bf59f468eb6d0d2cf8a41ef91': node_aadb373283133490}
