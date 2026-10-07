"""Small real CNN source; blocks are independently constructed."""

from torch import nn
from blocks import ResidualBlock


class ResidualCNN(nn.Module):
    def __init__(self, channels=16, classes=10):
        super().__init__()
        self.stem = nn.Conv2d(3, channels, 3, padding=1)
        self.blocks = nn.ModuleList([ResidualBlock(channels) for _ in range(2)])
        self.pool = nn.AdaptiveAvgPool2d(1)
        self.flatten = nn.Flatten(1)
        self.classifier = nn.Linear(channels, classes)

    def forward(self, image):
        x = self.stem(image)
        for block in self.blocks:
            x = block(x)
        x = self.flatten(self.pool(x))
        return self.classifier(x)
