"""Authored straight-line branches for the bounded input-rebinding contract."""

from torch import nn


class RebindDemo(nn.Module):
    def __init__(self):
        super().__init__()
        self.first = nn.Identity()
        self.activation = nn.GELU()
        self.branch = nn.ReLU()
        self.regularizer = nn.Dropout(0.1)
        self.output = nn.Identity()

    def forward(self, features):
        base = self.first(features)
        activated = self.activation(base)
        alternative = self.branch(base)
        regularized = self.regularizer(activated)
        result = self.output(regularized)
        return result
