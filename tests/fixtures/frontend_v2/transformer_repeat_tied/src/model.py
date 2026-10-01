from torch import nn


class Block:
    def __init__(self):
        self.projection = nn.Linear(16, 16)

    def forward(self, hidden):
        return self.projection(hidden)


class Model:
    def __init__(self):
        self.embedding = nn.Embedding(100, 16)
        self.layers = nn.ModuleList([Block() for _ in range(2)])
        self.projection = nn.Linear(16, 100, bias=False)
        self.projection.weight = self.embedding.weight

    def forward(self, tokens):
        hidden = self.embedding(tokens)
        for layer in self.layers:
            hidden = layer(hidden)
        return self.projection(hidden)
