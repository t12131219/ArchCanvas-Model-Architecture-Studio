import torch.nn as nn


class ChainModel(nn.Module):
    def __init__(self) -> None:
        super().__init__()
        self.embedding = nn.Embedding(32, 16)
        self.encoder = nn.Linear(16, 16)
        self.head = nn.Linear(16, 2)








    def forward(self, tokens):
        x = self.embedding(tokens)
        x = self.encoder(x)
        return self.head(x)
