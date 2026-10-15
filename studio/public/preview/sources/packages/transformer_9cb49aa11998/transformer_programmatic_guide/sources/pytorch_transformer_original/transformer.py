"""
PyTorch implementation of the original encoder-decoder Transformer architecture
from "Attention Is All You Need" (Vaswani et al., 2017).

Design goals:
- Educational and readable.
- Batch-first tensors: [batch, seq_len, d_model].
- Implements attention explicitly rather than wrapping nn.Transformer.
- Uses the original paper's Post-LayerNorm residual ordering:
      LayerNorm(x + Sublayer(x))
"""

from __future__ import annotations

import copy
import math
from typing import Optional

import torch
from torch import Tensor, nn


def clones(module: nn.Module, n: int) -> nn.ModuleList:
    """Create N independent copies of a module."""
    return nn.ModuleList([copy.deepcopy(module) for _ in range(n)])


def make_causal_mask(seq_len: int, device=None) -> Tensor:
    """
    Return a boolean causal mask of shape [seq_len, seq_len].

    True means "masked / not allowed to attend".
    Position i cannot attend to positions j > i.
    """
    return torch.triu(
        torch.ones(seq_len, seq_len, dtype=torch.bool, device=device),
        diagonal=1,
    )


def scaled_dot_product_attention(
    q: Tensor,
    k: Tensor,
    v: Tensor,
    attn_mask: Optional[Tensor] = None,
    key_padding_mask: Optional[Tensor] = None,
    dropout: Optional[nn.Dropout] = None,
) -> tuple[Tensor, Tensor]:
    """
    Scaled Dot-Product Attention.

    Shapes:
        q: [B, H, Tq, Dh]
        k: [B, H, Tk, Dh]
        v: [B, H, Tk, Dh]

        attn_mask:
            [Tq, Tk] or [B, Tq, Tk] or [B, H, Tq, Tk]
            bool tensor; True means masked.

        key_padding_mask:
            [B, Tk]
            bool tensor; True means padding / masked.

    Returns:
        output: [B, H, Tq, Dh]
        attention_weights: [B, H, Tq, Tk]
    """
    d_k = q.size(-1)
    scores = torch.matmul(q, k.transpose(-2, -1)) / math.sqrt(d_k)

    if attn_mask is not None:
        attn_mask = attn_mask.to(dtype=torch.bool, device=scores.device)

        if attn_mask.dim() == 2:
            attn_mask = attn_mask.unsqueeze(0).unsqueeze(0)   # [1,1,Tq,Tk]
        elif attn_mask.dim() == 3:
            attn_mask = attn_mask.unsqueeze(1)                # [B,1,Tq,Tk]
        elif attn_mask.dim() != 4:
            raise ValueError("attn_mask must have 2, 3, or 4 dimensions.")

        scores = scores.masked_fill(attn_mask, float("-inf"))

    if key_padding_mask is not None:
        key_padding_mask = key_padding_mask.to(
            dtype=torch.bool, device=scores.device
        )
        # [B, Tk] -> [B, 1, 1, Tk]
        padding = key_padding_mask.unsqueeze(1).unsqueeze(1)
        scores = scores.masked_fill(padding, float("-inf"))

    attention_weights = torch.softmax(scores, dim=-1)

    # Guard against a fully-masked row producing NaNs.
    attention_weights = torch.nan_to_num(attention_weights, nan=0.0)

    if dropout is not None:
        attention_weights = dropout(attention_weights)

    output = torch.matmul(attention_weights, v)
    return output, attention_weights


class MultiHeadAttention(nn.Module):
    """
    Multi-Head Attention from the original Transformer.

    MultiHead(Q,K,V) = Concat(head_1, ..., head_h) W^O
    head_i = Attention(Q W_i^Q, K W_i^K, V W_i^V)
    """

    def __init__(self, d_model: int = 512, num_heads: int = 8, dropout: float = 0.1):
        super().__init__()

        if d_model % num_heads != 0:
            raise ValueError("d_model must be divisible by num_heads.")

        self.d_model = d_model
        self.num_heads = num_heads
        self.d_head = d_model // num_heads

        self.w_q = nn.Linear(d_model, d_model)
        self.w_k = nn.Linear(d_model, d_model)
        self.w_v = nn.Linear(d_model, d_model)
        self.w_o = nn.Linear(d_model, d_model)

        self.attn_dropout = nn.Dropout(dropout)

    def _split_heads(self, x: Tensor) -> Tensor:
        # [B, T, D] -> [B, H, T, Dh]
        b, t, _ = x.shape
        return (
            x.view(b, t, self.num_heads, self.d_head)
            .transpose(1, 2)
            .contiguous()
        )

    def _combine_heads(self, x: Tensor) -> Tensor:
        # [B, H, T, Dh] -> [B, T, D]
        b, h, t, dh = x.shape
        return (
            x.transpose(1, 2)
            .contiguous()
            .view(b, t, h * dh)
        )

    def forward(
        self,
        query: Tensor,
        key: Tensor,
        value: Tensor,
        attn_mask: Optional[Tensor] = None,
        key_padding_mask: Optional[Tensor] = None,
        need_weights: bool = False,
    ):
        q = self._split_heads(self.w_q(query))
        k = self._split_heads(self.w_k(key))
        v = self._split_heads(self.w_v(value))

        x, weights = scaled_dot_product_attention(
            q=q,
            k=k,
            v=v,
            attn_mask=attn_mask,
            key_padding_mask=key_padding_mask,
            dropout=self.attn_dropout,
        )

        x = self._combine_heads(x)
        x = self.w_o(x)

        if need_weights:
            return x, weights
        return x


class PositionwiseFeedForward(nn.Module):
    """
    FFN(x) = max(0, x W1 + b1) W2 + b2

    Original base Transformer:
        d_model = 512
        d_ff    = 2048
    """

    def __init__(self, d_model: int = 512, d_ff: int = 2048, dropout: float = 0.1):
        super().__init__()
        self.linear1 = nn.Linear(d_model, d_ff)
        self.linear2 = nn.Linear(d_ff, d_model)
        self.dropout = nn.Dropout(dropout)
        self.activation = nn.ReLU()

    def forward(self, x: Tensor) -> Tensor:
        return self.linear2(self.dropout(self.activation(self.linear1(x))))


class PositionalEncoding(nn.Module):
    """
    Fixed sinusoidal positional encoding from the original paper.

    PE(pos, 2i)   = sin(pos / 10000^(2i/d_model))
    PE(pos, 2i+1) = cos(pos / 10000^(2i/d_model))
    """

    def __init__(
        self,
        d_model: int = 512,
        dropout: float = 0.1,
        max_len: int = 5000,
    ):
        super().__init__()
        self.dropout = nn.Dropout(dropout)

        position = torch.arange(max_len, dtype=torch.float32).unsqueeze(1)
        div_term = torch.exp(
            torch.arange(0, d_model, 2, dtype=torch.float32)
            * (-math.log(10000.0) / d_model)
        )

        pe = torch.zeros(max_len, d_model, dtype=torch.float32)
        pe[:, 0::2] = torch.sin(position * div_term)

        # Handles odd d_model as well.
        if d_model > 1:
            pe[:, 1::2] = torch.cos(
                position * div_term[: pe[:, 1::2].shape[1]]
            )

        self.register_buffer("pe", pe.unsqueeze(0), persistent=False)  # [1,L,D]

    def forward(self, x: Tensor) -> Tensor:
        x = x + self.pe[:, : x.size(1)].to(dtype=x.dtype)
        return self.dropout(x)


class TokenEmbedding(nn.Module):
    """Embedding multiplied by sqrt(d_model), as in the original paper."""

    def __init__(self, vocab_size: int, d_model: int):
        super().__init__()
        self.d_model = d_model
        self.embedding = nn.Embedding(vocab_size, d_model)

    def forward(self, token_ids: Tensor) -> Tensor:
        return self.embedding(token_ids) * math.sqrt(self.d_model)


class EncoderLayer(nn.Module):
    """
    Original encoder layer:

        x -> Self-Attention -> Add & Norm
          -> Feed Forward   -> Add & Norm
    """

    def __init__(
        self,
        d_model: int = 512,
        num_heads: int = 8,
        d_ff: int = 2048,
        dropout: float = 0.1,
    ):
        super().__init__()
        self.self_attn = MultiHeadAttention(d_model, num_heads, dropout)
        self.ffn = PositionwiseFeedForward(d_model, d_ff, dropout)

        self.norm1 = nn.LayerNorm(d_model)
        self.norm2 = nn.LayerNorm(d_model)

        self.dropout1 = nn.Dropout(dropout)
        self.dropout2 = nn.Dropout(dropout)

    def forward(
        self,
        x: Tensor,
        src_key_padding_mask: Optional[Tensor] = None,
    ) -> Tensor:
        attn_out = self.self_attn(
            query=x,
            key=x,
            value=x,
            key_padding_mask=src_key_padding_mask,
        )
        x = self.norm1(x + self.dropout1(attn_out))

        ffn_out = self.ffn(x)
        x = self.norm2(x + self.dropout2(ffn_out))
        return x


class Encoder(nn.Module):
    def __init__(self, layer: EncoderLayer, num_layers: int = 6):
        super().__init__()
        self.layers = clones(layer, num_layers)

    def forward(
        self,
        x: Tensor,
        src_key_padding_mask: Optional[Tensor] = None,
    ) -> Tensor:
        for layer in self.layers:
            x = layer(x, src_key_padding_mask=src_key_padding_mask)
        return x


class DecoderLayer(nn.Module):
    """
    Original decoder layer:

        x -> Masked Self-Attention -> Add & Norm
          -> Cross-Attention       -> Add & Norm
          -> Feed Forward          -> Add & Norm
    """

    def __init__(
        self,
        d_model: int = 512,
        num_heads: int = 8,
        d_ff: int = 2048,
        dropout: float = 0.1,
    ):
        super().__init__()

        self.self_attn = MultiHeadAttention(d_model, num_heads, dropout)
        self.cross_attn = MultiHeadAttention(d_model, num_heads, dropout)
        self.ffn = PositionwiseFeedForward(d_model, d_ff, dropout)

        self.norm1 = nn.LayerNorm(d_model)
        self.norm2 = nn.LayerNorm(d_model)
        self.norm3 = nn.LayerNorm(d_model)

        self.dropout1 = nn.Dropout(dropout)
        self.dropout2 = nn.Dropout(dropout)
        self.dropout3 = nn.Dropout(dropout)

    def forward(
        self,
        x: Tensor,
        memory: Tensor,
        tgt_mask: Optional[Tensor] = None,
        tgt_key_padding_mask: Optional[Tensor] = None,
        memory_key_padding_mask: Optional[Tensor] = None,
    ) -> Tensor:
        # 1) Masked decoder self-attention
        self_attn_out = self.self_attn(
            query=x,
            key=x,
            value=x,
            attn_mask=tgt_mask,
            key_padding_mask=tgt_key_padding_mask,
        )
        x = self.norm1(x + self.dropout1(self_attn_out))

        # 2) Encoder-decoder cross-attention
        cross_attn_out = self.cross_attn(
            query=x,
            key=memory,
            value=memory,
            key_padding_mask=memory_key_padding_mask,
        )
        x = self.norm2(x + self.dropout2(cross_attn_out))

        # 3) Position-wise FFN
        ffn_out = self.ffn(x)
        x = self.norm3(x + self.dropout3(ffn_out))
        return x


class Decoder(nn.Module):
    def __init__(self, layer: DecoderLayer, num_layers: int = 6):
        super().__init__()
        self.layers = clones(layer, num_layers)

    def forward(
        self,
        x: Tensor,
        memory: Tensor,
        tgt_mask: Optional[Tensor] = None,
        tgt_key_padding_mask: Optional[Tensor] = None,
        memory_key_padding_mask: Optional[Tensor] = None,
    ) -> Tensor:
        for layer in self.layers:
            x = layer(
                x=x,
                memory=memory,
                tgt_mask=tgt_mask,
                tgt_key_padding_mask=tgt_key_padding_mask,
                memory_key_padding_mask=memory_key_padding_mask,
            )
        return x


class Transformer(nn.Module):
    """
    Full encoder-decoder Transformer.

    Default dimensions correspond to Transformer-Base in the 2017 paper:
        N = 6
        d_model = 512
        d_ff = 2048
        h = 8
        dropout = 0.1
    """

    def __init__(
        self,
        src_vocab_size: int,
        tgt_vocab_size: int,
        d_model: int = 512,
        num_heads: int = 8,
        num_encoder_layers: int = 6,
        num_decoder_layers: int = 6,
        d_ff: int = 2048,
        dropout: float = 0.1,
        max_len: int = 5000,
        tie_tgt_embedding_and_generator: bool = False,
    ):
        super().__init__()

        self.src_embedding = TokenEmbedding(src_vocab_size, d_model)
        self.tgt_embedding = TokenEmbedding(tgt_vocab_size, d_model)
        self.position = PositionalEncoding(d_model, dropout, max_len)

        encoder_layer = EncoderLayer(d_model, num_heads, d_ff, dropout)
        decoder_layer = DecoderLayer(d_model, num_heads, d_ff, dropout)

        self.encoder = Encoder(encoder_layer, num_encoder_layers)
        self.decoder = Decoder(decoder_layer, num_decoder_layers)

        self.generator = nn.Linear(d_model, tgt_vocab_size, bias=False)

        if tie_tgt_embedding_and_generator:
            if self.generator.weight.shape != self.tgt_embedding.embedding.weight.shape:
                raise ValueError("Target embedding and generator shapes do not match.")
            self.generator.weight = self.tgt_embedding.embedding.weight

        self._reset_parameters()

    def _reset_parameters(self):
        # Xavier initialization for matrix parameters.
        for p in self.parameters():
            if p.dim() > 1:
                nn.init.xavier_uniform_(p)

    def encode(
        self,
        src: Tensor,
        src_key_padding_mask: Optional[Tensor] = None,
    ) -> Tensor:
        x = self.position(self.src_embedding(src))
        return self.encoder(x, src_key_padding_mask)

    def decode(
        self,
        tgt: Tensor,
        memory: Tensor,
        tgt_mask: Optional[Tensor] = None,
        tgt_key_padding_mask: Optional[Tensor] = None,
        memory_key_padding_mask: Optional[Tensor] = None,
    ) -> Tensor:
        x = self.position(self.tgt_embedding(tgt))
        return self.decoder(
            x=x,
            memory=memory,
            tgt_mask=tgt_mask,
            tgt_key_padding_mask=tgt_key_padding_mask,
            memory_key_padding_mask=memory_key_padding_mask,
        )

    def forward(
        self,
        src: Tensor,
        tgt: Tensor,
        src_key_padding_mask: Optional[Tensor] = None,
        tgt_key_padding_mask: Optional[Tensor] = None,
        tgt_mask: Optional[Tensor] = None,
    ) -> Tensor:
        """
        Args:
            src: [B, S]
            tgt: [B, T]
            src_key_padding_mask: [B, S], True at PAD positions
            tgt_key_padding_mask: [B, T], True at PAD positions
            tgt_mask: [T, T], True where attention is forbidden

        Returns:
            logits: [B, T, tgt_vocab_size]
        """
        memory = self.encode(src, src_key_padding_mask)

        decoder_out = self.decode(
            tgt=tgt,
            memory=memory,
            tgt_mask=tgt_mask,
            tgt_key_padding_mask=tgt_key_padding_mask,
            memory_key_padding_mask=src_key_padding_mask,
        )

        return self.generator(decoder_out)


@torch.no_grad()
def greedy_decode(
    model: Transformer,
    src: Tensor,
    bos_id: int,
    eos_id: int,
    max_new_tokens: int,
    pad_id: Optional[int] = None,
) -> Tensor:
    """
    Minimal greedy autoregressive decoder.

    This is intentionally simple and does not implement KV caching.
    """
    model.eval()

    if pad_id is None:
        src_padding_mask = None
    else:
        src_padding_mask = src.eq(pad_id)

    memory = model.encode(src, src_padding_mask)

    ys = torch.full(
        (src.size(0), 1),
        bos_id,
        dtype=torch.long,
        device=src.device,
    )

    finished = torch.zeros(src.size(0), dtype=torch.bool, device=src.device)

    for _ in range(max_new_tokens):
        causal_mask = make_causal_mask(ys.size(1), device=ys.device)

        decoder_out = model.decode(
            tgt=ys,
            memory=memory,
            tgt_mask=causal_mask,
            memory_key_padding_mask=src_padding_mask,
        )

        next_token_logits = model.generator(decoder_out[:, -1, :])
        next_token = next_token_logits.argmax(dim=-1)

        ys = torch.cat([ys, next_token.unsqueeze(1)], dim=1)

        finished |= next_token.eq(eos_id)
        if finished.all():
            break

    return ys
