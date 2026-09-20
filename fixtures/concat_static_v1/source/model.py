import torch
import torch.nn as nn


class FusionModel(nn.Module):
    def __init__(self) -> None:
        super().__init__()
        self.left = nn.Linear(4, 4)
        self.right = nn.Linear(4, 4)
        self.proj = nn.Linear(8, 2)

    def forward(self, x):
        left = self.left(x)
        right = self.right(x)
        merged = torch.cat([left, right], dim=-1)
        return self.proj(merged)
