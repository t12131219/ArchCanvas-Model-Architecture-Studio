import torch.nn as nn


class EncoderModel(nn.Module):
    def __init__(
        self,
        vocab: int = 32000,
        d_model: int = 256,
        depth: int = 6,
        classes: int = 4,
    ) -> None:
        super().__init__()
        self.embedding = nn.Embedding(vocab, d_model)
        self.layers = nn.ModuleList(
            [
                nn.TransformerEncoderLayer(
                    d_model=d_model,
                    nhead=8,  # edited by the v1 fixture
                    dropout=0.1,
                    batch_first=True,
                )
                for _ in range(depth)
            ]
        )
        self.norm = nn.LayerNorm(d_model)
        self.head = nn.Linear(d_model, classes)

    def forward(self, tokens):
        x = self.embedding(tokens)
        for layer in self.layers:
            x = layer(x)
        x = self.norm(x)
        x = x.mean(dim=1)
        return self.head(x)
