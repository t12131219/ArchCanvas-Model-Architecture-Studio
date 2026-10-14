"""
Compact equivalent using PyTorch's built-in nn.Transformer.

Use this file when you want to compare the from-scratch implementation
(transformer.py) against PyTorch's reference Transformer API.
"""

import math
import torch
from torch import nn


class PyTorchBuiltinTransformer(nn.Module):
    def __init__(
        self,
        src_vocab_size: int,
        tgt_vocab_size: int,
        d_model: int = 512,
        nhead: int = 8,
        num_encoder_layers: int = 6,
        num_decoder_layers: int = 6,
        dim_feedforward: int = 2048,
        dropout: float = 0.1,
        max_len: int = 5000,
    ):
        super().__init__()

        self.d_model = d_model

        self.src_embedding = nn.Embedding(src_vocab_size, d_model)
        self.tgt_embedding = nn.Embedding(tgt_vocab_size, d_model)

        position = torch.arange(max_len).unsqueeze(1)
        div_term = torch.exp(
            torch.arange(0, d_model, 2)
            * (-math.log(10000.0) / d_model)
        )
        pe = torch.zeros(max_len, d_model)
        pe[:, 0::2] = torch.sin(position * div_term)
        pe[:, 1::2] = torch.cos(
            position * div_term[: pe[:, 1::2].shape[1]]
        )
        self.register_buffer("pe", pe.unsqueeze(0), persistent=False)

        self.transformer = nn.Transformer(
            d_model=d_model,
            nhead=nhead,
            num_encoder_layers=num_encoder_layers,
            num_decoder_layers=num_decoder_layers,
            dim_feedforward=dim_feedforward,
            dropout=dropout,
            activation="relu",
            batch_first=True,
            norm_first=False,   # Post-LN ordering, closer to the 2017 paper.
        )

        self.generator = nn.Linear(d_model, tgt_vocab_size)

    def forward(
        self,
        src,
        tgt,
        src_key_padding_mask=None,
        tgt_key_padding_mask=None,
    ):
        src_len = src.size(1)
        tgt_len = tgt.size(1)

        src_x = (
            self.src_embedding(src) * math.sqrt(self.d_model)
            + self.pe[:, :src_len]
        )
        tgt_x = (
            self.tgt_embedding(tgt) * math.sqrt(self.d_model)
            + self.pe[:, :tgt_len]
        )

        # nn.Transformer supports causal decoding directly.
        out = self.transformer(
            src=src_x,
            tgt=tgt_x,
            src_key_padding_mask=src_key_padding_mask,
            tgt_key_padding_mask=tgt_key_padding_mask,
            memory_key_padding_mask=src_key_padding_mask,
            tgt_is_causal=True,
        )

        return self.generator(out)


if __name__ == "__main__":
    model = PyTorchBuiltinTransformer(
        src_vocab_size=100,
        tgt_vocab_size=120,
        d_model=128,
        nhead=8,
        num_encoder_layers=2,
        num_decoder_layers=2,
        dim_feedforward=512,
    )

    src = torch.randint(0, 100, (2, 10))
    tgt = torch.randint(0, 120, (2, 7))

    logits = model(src, tgt)
    print(logits.shape)
