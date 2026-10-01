from torch import nn


class ConvBlock:
    def __init__(self):
        self.conv = nn.Conv2d(3, 16, 3)
        self.relu = nn.ReLU()

    def forward(self, x):
        x = self.conv(x)
        return self.relu(x)
