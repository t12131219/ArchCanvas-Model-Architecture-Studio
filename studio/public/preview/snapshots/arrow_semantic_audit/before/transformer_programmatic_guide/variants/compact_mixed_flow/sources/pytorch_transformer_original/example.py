import torch

from transformer import Transformer, make_causal_mask, greedy_decode


def main():
    torch.manual_seed(42)

    PAD = 0
    BOS = 1
    EOS = 2

    src_vocab_size = 100
    tgt_vocab_size = 120

    # Smaller dimensions than the paper so this example runs quickly on CPU.
    model = Transformer(
        src_vocab_size=src_vocab_size,
        tgt_vocab_size=tgt_vocab_size,
        d_model=128,
        num_heads=8,
        num_encoder_layers=2,
        num_decoder_layers=2,
        d_ff=512,
        dropout=0.1,
    )

    # [batch, src_len]
    src = torch.tensor([
        [5, 7, 9, 11, 13, 0, 0],
        [4, 6, 8, 10, 12, 14, 16],
    ])

    # Teacher-forcing decoder input.
    # [BOS, y1, y2, ...]
    tgt_in = torch.tensor([
        [BOS, 20, 21, 22, 0],
        [BOS, 30, 31, 32, 33],
    ])

    src_padding_mask = src.eq(PAD)
    tgt_padding_mask = tgt_in.eq(PAD)
    causal_mask = make_causal_mask(tgt_in.size(1), device=tgt_in.device)

    logits = model(
        src=src,
        tgt=tgt_in,
        src_key_padding_mask=src_padding_mask,
        tgt_key_padding_mask=tgt_padding_mask,
        tgt_mask=causal_mask,
    )

    print("src shape:   ", tuple(src.shape))
    print("tgt shape:   ", tuple(tgt_in.shape))
    print("logits shape:", tuple(logits.shape))
    print("Expected:    ", (2, 5, tgt_vocab_size))

    generated = greedy_decode(
        model=model,
        src=src,
        bos_id=BOS,
        eos_id=EOS,
        max_new_tokens=8,
        pad_id=PAD,
    )

    print("greedy output shape:", tuple(generated.shape))
    print(generated)


if __name__ == "__main__":
    main()
