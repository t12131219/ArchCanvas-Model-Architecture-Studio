"""Small Transformer path fixture. ArchCanvas must parse this file without importing it."""

import torch
from torch import nn


class Transformer(nn.Module):
    def __init__(self, d_model: int = 64, num_heads: int = 8, vocab_size: int = 32000):
        super().__init__()
        self.num_heads = num_heads
        self.encoder_q_proj = nn.Linear(d_model, d_model)
        self.encoder_k_proj = nn.Linear(d_model, d_model)
        self.encoder_v_proj = nn.Linear(d_model, d_model)
        self.encoder_out_proj = nn.Linear(d_model, d_model)
        self.encoder_norm = nn.LayerNorm(d_model)
        self.decoder_q_proj = nn.Linear(d_model, d_model)
        self.decoder_k_proj = nn.Linear(d_model, d_model)
        self.decoder_v_proj = nn.Linear(d_model, d_model)
        self.decoder_out_proj = nn.Linear(d_model, d_model)
        self.decoder_norm = nn.LayerNorm(d_model)
        self.cross_q_proj = nn.Linear(d_model, d_model)
        self.cross_k_proj = nn.Linear(d_model, d_model)
        self.cross_v_proj = nn.Linear(d_model, d_model)
        self.cross_out_proj = nn.Linear(d_model, d_model)
        self.cross_norm = nn.LayerNorm(d_model)
        self.ffn_in = nn.Linear(d_model, d_model * 4)
        self.activation = nn.GELU()
        self.ffn_out = nn.Linear(d_model * 4, d_model)
        self.output_norm = nn.LayerNorm(d_model)
        self.generator = nn.Linear(d_model, vocab_size)

    def forward(self, src, tgt, target_mask):
        enc_q = self.encoder_q_proj(src)
        enc_k = self.encoder_k_proj(src)
        enc_v = self.encoder_v_proj(src)
        enc_k_t = enc_k.transpose(-2, -1)
        enc_scores = torch.matmul(enc_q, enc_k_t)
        enc_weights = torch.softmax(enc_scores, dim=-1)
        enc_context = torch.matmul(enc_weights, enc_v)
        enc_attention = self.encoder_out_proj(enc_context)
        enc_residual = src + enc_attention
        memory = self.encoder_norm(enc_residual)

        dec_q = self.decoder_q_proj(tgt)
        dec_k = self.decoder_k_proj(tgt)
        dec_v = self.decoder_v_proj(tgt)
        dec_k_t = dec_k.transpose(-2, -1)
        dec_scores = torch.matmul(dec_q, dec_k_t)
        masked_scores = dec_scores.masked_fill(target_mask == 0, -1e9)
        dec_weights = torch.softmax(masked_scores, dim=-1)
        dec_context = torch.matmul(dec_weights, dec_v)
        dec_attention = self.decoder_out_proj(dec_context)
        dec_residual = tgt + dec_attention
        decoder_hidden = self.decoder_norm(dec_residual)

        cross_q = self.cross_q_proj(decoder_hidden)
        cross_k = self.cross_k_proj(memory)
        cross_v = self.cross_v_proj(memory)
        cross_k_t = cross_k.transpose(-2, -1)
        cross_scores = torch.matmul(cross_q, cross_k_t)
        cross_weights = torch.softmax(cross_scores, dim=-1)
        cross_context = torch.matmul(cross_weights, cross_v)
        cross_attention = self.cross_out_proj(cross_context)
        cross_residual = decoder_hidden + cross_attention
        cross_hidden = self.cross_norm(cross_residual)

        expanded = self.ffn_in(cross_hidden)
        activated = self.activation(expanded)
        transformed = self.ffn_out(activated)
        output_residual = cross_hidden + transformed
        output_hidden = self.output_norm(output_residual)
        logits = self.generator(output_hidden)
        return logits

