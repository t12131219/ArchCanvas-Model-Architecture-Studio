"""Small original validation models; not copied from reference collections."""
import torch
from torch import nn


class BranchMLP(nn.Module):
    def __init__(self):
        super().__init__()
        self.first = nn.Linear(4, 6)
        self.left = nn.Linear(6, 2)
        self.right = nn.Linear(6, 2)

    def forward(self, x, positive=False):
        hidden = torch.relu(self.first(x))
        if positive:
            y = self.left(hidden)
        else:
            y = self.right(hidden)
        return y


class TinyCNN(nn.Module):
    def __init__(self):
        super().__init__()
        self.conv = nn.Conv2d(1, 3, 3)
        self.pool = nn.AdaptiveAvgPool2d((1, 1))
        self.head = nn.Linear(3, 2)

    def forward(self, image):
        features = self.conv(image)
        activated = torch.relu(features)
        pooled = self.pool(activated)
        return self.head(pooled.flatten(1))


class ReusedRecurrent(nn.Module):
    def __init__(self):
        super().__init__()
        self.recurrent = nn.LSTM(3, 4, batch_first=True)
        self.shared = nn.Linear(4, 4)
        self.alias = self.shared

    def forward(self, sequence):
        sequence_out, state = self.recurrent(sequence)
        first = self.shared(sequence_out)
        second = self.alias(first)
        return second, state


class UnknownCall(nn.Module):
    def forward(self, x):
        return custom_external(x)


def build_model():
    return BranchMLP(**{})
