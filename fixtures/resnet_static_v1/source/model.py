import torch.nn as nn


class ResidualBlock(nn.Module):
    def __init__(self, channels: int = 16) -> None:
        super().__init__()
        self.conv1 = nn.Conv2d(channels, channels, kernel_size=3, padding=1)
        self.conv2 = nn.Conv2d(channels, channels, kernel_size=3, padding=1)
        self.relu = nn.ReLU()

    def forward(self, x):
        x = self.conv1(x)
        identity = x
        out = self.conv2(x)
        out = out + identity
        return self.relu(out)
