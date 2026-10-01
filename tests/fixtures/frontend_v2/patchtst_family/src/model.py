from torch import nn


class PatchTST(nn.Module):
    def __init__(self):
        super().__init__()
        self.projection = nn.Linear(8, 8)

    def forward(self, inputs):
        return self.projection(inputs)
