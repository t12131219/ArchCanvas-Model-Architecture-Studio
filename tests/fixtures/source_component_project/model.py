from torch import nn
from layers import ExternalFeedForward


class ProjectEncoder(nn.Module):
    def __init__(self, width=16):
        super().__init__()
        self.block = ExternalFeedForward(width)
        self.norm = nn.LayerNorm(width)

    def forward(self, x):
        return self.norm(self.block(x) + x)
