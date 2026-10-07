"""A compact real encoder–decoder model; no template-generated graph facts."""

from torch import nn
from blocks import DecoderLayer, EncoderLayer


class Transformer(nn.Module):
    def __init__(self, vocab_size=128, d_model=32, n_heads=4, n_layers=2):
        super().__init__()
        self.source_embedding = nn.Embedding(vocab_size, d_model)
        self.target_embedding = nn.Embedding(vocab_size, d_model)
        self.encoder = nn.ModuleList([EncoderLayer(d_model, n_heads) for _ in range(n_layers)])
        self.decoder = DecoderLayer(d_model, n_heads)
        self.output_projection = nn.Linear(d_model, vocab_size)

    def forward(self, source_tokens, target_tokens, source_mask=None, target_mask=None, memory_mask=None):
        memory = self.source_embedding(source_tokens)
        for layer in self.encoder:
            memory = layer(memory, mask=source_mask)
        target = self.target_embedding(target_tokens)
        hidden = self.decoder(target, memory, target_mask=target_mask, memory_mask=memory_mask)
        return self.output_projection(hidden)
