from torch import nn


class ExternalFeedForward(nn.Module):
    def __init__(self, width=16):
        super().__init__()
        self.input = nn.Linear(width, width * 2)
        self.activation = nn.GELU()
        self.output = nn.Linear(width * 2, width)

    def forward(self, x):
        return self.output(self.activation(self.input(x)))
