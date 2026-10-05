"""Independent M4 temporal, skip-network and unknown/dynamic holdouts.

These are hand-authored source inputs, not graph templates. The unresolved
semantic kernels below deliberately have callable Python names without a
registered framework contract; static analysis must keep their calls opaque.
"""

import torch
from torch import nn


class TemporalForecaster(nn.Module):
    def __init__(self):
        super().__init__()
        self.recurrent = nn.LSTM(6, 8, num_layers=2, batch_first=True)
        self.projection = nn.Linear(8, 3)
        self.shared_projection = self.projection

    def forward(self, series):
        sequence, (hidden, cell) = self.recurrent(series)
        primary = self.projection(sequence)
        secondary = self.shared_projection(sequence)
        return {"forecast": (primary, secondary), "state": {"hidden": hidden, "cell": cell}}


class ConvRefinement(nn.Module):
    def __init__(self, channels=8):
        super().__init__()
        self.conv = nn.Conv2d(channels, channels, 3, padding=1)
        self.activation = nn.ReLU()

    def forward(self, image):
        return self.activation(self.conv(image))


class SkipSegmentation(nn.Module):
    """A U-Net-style skip/concat source; transposed convolution is opaque."""

    def __init__(self):
        super().__init__()
        self.stem = nn.Conv2d(3, 8, 3, padding=1)
        self.refinement = nn.ModuleList([ConvRefinement(8) for _ in range(2)])
        self.downsample = nn.MaxPool2d(2)
        self.bottleneck = nn.Conv2d(8, 16, 3, padding=1)
        self.upsample = nn.ConvTranspose2d(16, 8, 2, stride=2)
        self.head = nn.Conv2d(16, 2, 1)

    def forward(self, image):
        skip = self.stem(image)
        for block in self.refinement:
            skip = block(skip)
        coarse = self.bottleneck(self.downsample(skip))
        restored = self.upsample(coarse)
        merged = torch.cat((skip, restored), dim=1)
        return self.head(merged)


class GraphAttentionKernel:
    """This callable has no registered PyTorch contract despite its name."""

    def __call__(self, nodes, edge_index):
        return nodes


class StateSpaceScan:
    """This callable has no registered recurrent/state-space contract."""

    def __call__(self, sequence):
        return sequence


class GraphForecast(nn.Module):
    def __init__(self):
        super().__init__()
        self.project = nn.Linear(4, 4)
        self.message = GraphAttentionKernel()
        self.activation = nn.ReLU()

    def forward(self, nodes, edge_index):
        features = self.project(nodes)
        messages = self.message(features, edge_index)
        if features.sum() > 0:
            messages = self.activation(messages)
        return messages


class DynamicStateSpace(nn.Module):
    def __init__(self):
        super().__init__()
        self.scan = StateSpaceScan()
        self.projection = nn.Linear(4, 4)

    def forward(self, sequence):
        state = self.scan(sequence)
        for index in range(sequence.shape[1]):
            state = self.projection(state)
        return state
