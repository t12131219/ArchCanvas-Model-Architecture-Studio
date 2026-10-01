from torch import nn


class EncoderLayer:
    def __init__(self):
        self.attention = nn.MultiheadAttention(16, 4, batch_first=True)

    def forward(self, hidden, padding_mask):
        context, _ = self.attention(
            hidden,
            hidden,
            hidden,
            key_padding_mask=padding_mask,
        )
        return context


class DecoderLayer:
    def __init__(self):
        self.cross_attention = nn.MultiheadAttention(16, 4, batch_first=True)

    def forward(self, hidden, memory, padding_mask):
        context, _ = self.cross_attention(
            query=hidden,
            key=memory,
            value=memory,
            key_padding_mask=padding_mask,
        )
        return context


class Transformer:
    def __init__(self):
        self.embedding = nn.Embedding(100, 16)
        self.encoder_layers = nn.ModuleList([EncoderLayer() for _ in range(2)])
        self.decoder_layers = nn.ModuleList([DecoderLayer() for _ in range(3)])
        self.generator = nn.Linear(16, 100, bias=False)
        self.generator.weight = self.embedding.weight

    def forward(self, source_tokens, target_tokens, source_padding_mask):
        memory = self.embedding(source_tokens)
        for layer in self.encoder_layers:
            memory = layer(memory, source_padding_mask)
        hidden = self.embedding(target_tokens)
        for layer in self.decoder_layers:
            hidden = layer(hidden, memory, source_padding_mask)
        return self.generator(hidden)
