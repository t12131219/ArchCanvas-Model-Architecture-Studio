from torch import nn


class Model:
    def __init__(self):
        self.attention = nn.MultiheadAttention(32, 4, batch_first=True)

    def forward(self, hidden, mask):
        context, weights = self.attention(
            value=hidden,
            attn_mask=mask,
            query=hidden,
            key=hidden,
        )
        _ = weights
        return context
