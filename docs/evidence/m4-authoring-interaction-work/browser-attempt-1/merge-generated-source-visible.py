"""Fresh ArchCanvas authored model; static declarations are not runtime verification."""
import torch
from torch import nn


class AuthoredModel(nn.Module):
    def __init__(self):
        super().__init__()

    def forward(self, node_5a0f6831111e46e6, node_d579c42eb69e57d4):
        node_f666a9fdc70bb0ef = node_5a0f6831111e46e6 + node_d579c42eb69e57d4
        node_710e76866cbd85b5 = torch.cat((node_f666a9fdc70bb0ef, node_5a0f6831111e46e6), dim=1)
        return {'n_9e49f606b49445758b384331e119d7bc': node_710e76866cbd85b5}
