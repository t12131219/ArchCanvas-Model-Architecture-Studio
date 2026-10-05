"""Explicit multi-input attention for structural connection review and replay."""
from torch import nn


class MultiInputAttention(nn.Module):
    def __init__(self):
        super().__init__()
        self.query_path = nn.Identity()
        self.memory_path = nn.Identity()
        self.alternative_path = nn.Identity()
        self.attention = nn.MultiheadAttention(8, 2, dropout=0.1, batch_first=True)
        self.output_path = nn.Identity()

    def forward(self, query, memory, alternative, padding_mask):
        q = self.query_path(query)
        k = self.memory_path(memory)
        alternate = self.alternative_path(alternative)
        attended, weights = self.attention(q, k, k, key_padding_mask=padding_mask, need_weights=False)
        result = self.output_path(attended)
        return result
