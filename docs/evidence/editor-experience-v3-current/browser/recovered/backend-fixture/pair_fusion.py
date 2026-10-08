from torch import nn

class PairFusion(nn.Module):
    def __init__(self, width=4, bias=False):
        super().__init__()
        self.project = nn.Linear(width, width, bias=bias)

    def forward(self, left, *, right):
        return self.project(left), right
