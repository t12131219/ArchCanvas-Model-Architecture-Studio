from .api import Conv


class Model:
    def __init__(self):
        self.conv = Conv(3, 8, 3)

    def forward(self, x):
        return self.conv(x)
