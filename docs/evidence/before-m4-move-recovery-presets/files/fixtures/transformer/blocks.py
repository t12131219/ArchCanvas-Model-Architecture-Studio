"""Hand-authored PyTorch source fixture. Analysis never imports this module."""

from torch import nn


class FeedForward(nn.Module):
    def __init__(self, d_model=32, d_hidden=64, dropout=0.1):
        super().__init__()
        self.expand = nn.Linear(d_model, d_hidden)
        self.activation = nn.GELU()
        self.dropout = nn.Dropout(dropout)
        self.project = nn.Linear(d_hidden, d_model)

    def forward(self, x):
        return self.project(self.dropout(self.activation(self.expand(x))))


class EncoderLayer(nn.Module):
    def __init__(self, d_model=32, n_heads=4, dropout=0.1):
        super().__init__()
        self.self_attention = nn.MultiheadAttention(d_model, n_heads, dropout=dropout, batch_first=True)
        self.attention_dropout = nn.Dropout(dropout)
        self.attention_norm = nn.LayerNorm(d_model)
        self.feedforward = FeedForward(d_model, d_model * 2, dropout)
        self.feedforward_norm = nn.LayerNorm(d_model)

    def forward(self, x, mask=None):
        attended, weights = self.self_attention(query=x, key=x, value=x, attn_mask=mask, need_weights=False)
        x = self.attention_norm(x + self.attention_dropout(attended))
        return self.feedforward_norm(x + self.feedforward(x))


class DecoderLayer(nn.Module):
    def __init__(self, d_model=32, n_heads=4, dropout=0.1):
        super().__init__()
        self.self_attention = nn.MultiheadAttention(d_model, n_heads, dropout=dropout, batch_first=True)
        self.self_norm = nn.LayerNorm(d_model)
        self.cross_attention = nn.MultiheadAttention(d_model, n_heads, dropout=dropout, batch_first=True)
        self.cross_norm = nn.LayerNorm(d_model)
        self.feedforward = FeedForward(d_model, d_model * 2, dropout)
        self.feedforward_norm = nn.LayerNorm(d_model)

    def forward(self, x, memory, target_mask=None, memory_mask=None):
        attended, weights = self.self_attention(query=x, key=x, value=x, attn_mask=target_mask, need_weights=False)
        x = self.self_norm(x + attended)
        attended, weights = self.cross_attention(query=x, key=memory, value=memory, attn_mask=memory_mask, need_weights=False)
        x = self.cross_norm(x + attended)
        return self.feedforward_norm(x + self.feedforward(x))
