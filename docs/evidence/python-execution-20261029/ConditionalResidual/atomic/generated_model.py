"""Original algebra, convolution, vector and context composition examples."""
import math
import torch
from torch import nn


def combine_values(a, b, c):
    scores = torch.matmul(a, b.transpose(-2, -1)) / math.sqrt(a.size(-1))
    weights = torch.softmax(scores, dim=-1)
    return torch.matmul(weights, c)


class ProjectedMixer(nn.Module):
    def __init__(self, width=8, parts=2):
        super().__init__()
        self.parts = parts
        self.chunk = width // parts
        self.left = nn.Linear(width, width)
        self.right = nn.Linear(width, width)
        self.signal = nn.Linear(width, width)
        self.finish = nn.Linear(width, width)

    def divide(self, x):
        batch, length, _ = x.shape
        return x.view(batch, length, self.parts, self.chunk).transpose(1, 2).contiguous()

    def collect(self, x):
        batch, parts, length, chunk = x.shape
        return x.transpose(1, 2).contiguous().view(batch, length, parts * chunk)

    def forward(self, x, context, values):
        a = self.divide(self.left(x))
        b = self.divide(self.right(context))
        c = self.divide(self.signal(values))
        result = combine_values(a, b, c)
        return self.finish(self.collect(result))


class SameSource(nn.Module):
    def __init__(self):
        super().__init__()
        self.mixer = ProjectedMixer()

    def forward(self, x):
        return self.mixer(x, x, x)


class TwoSources(nn.Module):
    def __init__(self):
        super().__init__()
        self.mixer = ProjectedMixer()

    def forward(self, x, context):
        return self.mixer(x, context, context)


class VectorBlock(nn.Module):
    def __init__(self):
        super().__init__()
        self.first = nn.Linear(8, 16)
        self.dropout = nn.Dropout(0.1)
        self.second = nn.Linear(16, 8)

    def forward(self, x):
        return self.second(self.dropout(torch.relu(self.first(x))))


class ImageResidual(nn.Module):
    def __init__(self):
        super().__init__()
        self.first = nn.Conv2d(4, 4, 3, padding=1)
        self.second = nn.Conv2d(4, 4, 3, padding=1)
        self.norm = nn.BatchNorm2d(4)

    def forward(self, x):
        transformed = self.second(torch.relu(self.first(x)))
        return self.norm(x + transformed)


class VectorResidual(nn.Module):
    def __init__(self):
        super().__init__()
        self.norm = nn.LayerNorm(8)
        self.block = VectorBlock()

    def forward(self, x):
        return x + self.block(self.norm(x))


class ConditionalResidual(nn.Module):
    def __init__(self):
        super().__init__()
        self.left = nn.Linear(8, 8)
        self.right = nn.Linear(8, 8)

    def forward(self, x, other, flag):
        if flag:
            y = self.left(x)
        else:
            y = self.right(other)
        return x + y


class ChosenOutput(nn.Module):
    def forward(self, x, details=False):
        if details:
            return x, x.relu()
        return x


class ExplicitChoice(nn.Module):
    def __init__(self):
        super().__init__()
        self.block = ChosenOutput()

    def forward(self, x):
        return self.block(x, details=True)


def build_model():
    return ConditionalResidual(**{})
