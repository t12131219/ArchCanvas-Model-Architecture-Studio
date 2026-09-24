"""Unseen graph message-passing block used for generic recovery acceptance."""

from torch import nn


class NeighborhoodExchange(nn.Module):
    def __init__(self, features: int = 20):
        super().__init__()
        self.node_projection = nn.Linear(features, features)
        self.neighbor_projection = nn.Linear(features, features)
        self.update = nn.ReLU()

    def forward(self, nodes, neighbors):
        local = self.node_projection(nodes)
        message = self.neighbor_projection(neighbors)
        aggregated = local + message
        updated = self.update(aggregated)
        return updated
