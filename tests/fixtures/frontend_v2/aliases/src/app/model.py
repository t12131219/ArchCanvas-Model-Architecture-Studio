import torch
import torch.nn as nn  # noqa: PLR0402 - resolver fixture covers this common spelling.
from torch.nn import Linear
from torch.nn import Linear as Dense

from .api import ReexportedLinear


class Model:
    def __init__(self):
        self.from_nn = nn.Linear(8, 8)
        self.from_torch = torch.nn.Linear(8, 8)
        self.from_direct = Linear(8, 8)
        self.from_alias = Dense(8, 8)
        self.from_reexport = ReexportedLinear(8, 8)

    def forward(self, x):
        x = self.from_nn(x)
        x = self.from_torch(x)
        x = self.from_direct(x)
        x = self.from_alias(x)
        return self.from_reexport(x)
