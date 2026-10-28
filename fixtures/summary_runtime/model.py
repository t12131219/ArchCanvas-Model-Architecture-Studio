from torch import nn


class RuntimeFixture(nn.Module):
    def __init__(self, width=3):
        super().__init__()
        # Deliberately dynamic constructor: static analysis keeps the boundary.
        self.projection = getattr(nn, 'Linear')(width, width, bias=False)

    def forward(self, x, flag):
        left = self.projection(x)
        right = self.projection(x)
        if flag:
            return left + right
        return left - right
