"""Source fixture with a registered Sequential construction contract."""

from torch import nn


class MLP(nn.Module):
    def __init__(self, input_dim=16, hidden_dim=32, output_dim=4):
        super().__init__()
        self.network = nn.Sequential(
            nn.Linear(input_dim, hidden_dim),
            nn.GELU(),
            nn.Dropout(0.1),
            nn.Linear(hidden_dim, output_dim),
        )

    def forward(self, features):
        return self.network(features)
