"""Unseen bounded expert router used for generic recovery acceptance."""

from torch import nn


class DualExpertRouter(nn.Module):
    def __init__(self, d_model: int = 28):
        super().__init__()
        self.router = nn.Linear(d_model, 2)
        self.expert_a = nn.Linear(d_model, d_model)
        self.expert_b = nn.Linear(d_model, d_model)
        self.output = nn.Linear(d_model, d_model)

    def forward(self, tokens):
        routing = self.router(tokens)
        first = self.expert_a(tokens)
        second = self.expert_b(tokens)
        combined = first + second
        projected = self.output(combined)
        return projected
