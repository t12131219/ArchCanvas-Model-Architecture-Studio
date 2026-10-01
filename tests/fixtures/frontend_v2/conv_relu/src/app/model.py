from .blocks import ConvBlock


class Model:
    def __init__(self):
        self.block = ConvBlock()

    def forward(self, x):
        return self.block(x)
