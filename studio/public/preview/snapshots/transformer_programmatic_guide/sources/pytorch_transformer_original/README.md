# PyTorch Transformer — 2017 Original Architecture

这是一个面向学习与源码阅读的 PyTorch Transformer 实现，结构对应：

**Vaswani et al., 2017 — _Attention Is All You Need_**

核心实现没有直接调用 `nn.Transformer`，而是显式写出：

- Scaled Dot-Product Attention
- Multi-Head Attention
- Sinusoidal Positional Encoding
- Position-wise Feed-Forward Network
- Encoder Layer
- Decoder Layer
- Masked Self-Attention
- Encoder–Decoder Cross-Attention
- Residual Connection + LayerNorm
- Encoder / Decoder 堆叠
- Linear vocabulary projection
- Causal Mask
- Padding Mask
- Greedy autoregressive decoding

另外附带 `torch_builtin_version.py`，用于和 PyTorch 官方 `nn.Transformer`
参考实现进行对照。

---

## 文件结构

```text
pytorch_transformer_original/
├── transformer.py
├── example.py
├── torch_builtin_version.py
├── requirements.txt
└── README.md
```

---

## Transformer-Base 参数

论文中的 Base 配置：

```text
N encoder layers = 6
N decoder layers = 6

d_model = 512
d_ff = 2048
num_heads = 8
d_head = 64

dropout = 0.1
```

代码中 `Transformer(...)` 的默认参数正是这些值。

---

## 安装

```bash
python -m venv .venv

# Linux / macOS
source .venv/bin/activate

# Windows PowerShell
# .venv\Scripts\Activate.ps1

pip install -r requirements.txt
```

---

## 快速运行

```bash
python example.py
```

示例为了 CPU 快速执行，将模型缩小为：

```python
model = Transformer(
    src_vocab_size=100,
    tgt_vocab_size=120,
    d_model=128,
    num_heads=8,
    num_encoder_layers=2,
    num_decoder_layers=2,
    d_ff=512,
)
```

实际学习论文结构时，可以直接恢复默认 Base 参数。

---

## 主数据流

```text
src token ids
    │
    ▼
Token Embedding × sqrt(d_model)
    │
    ▼
+ Positional Encoding
    │
    ▼
┌──────────────────────────────┐
│ Encoder Layer × N            │
│                              │
│ Multi-Head Self-Attention    │
│          ↓                   │
│      Add & Norm              │
│          ↓                   │
│ Feed-Forward Network         │
│          ↓                   │
│      Add & Norm              │
└──────────────────────────────┘
    │
    ▼
encoder memory
    │
    │
    ├──────────────────────────────┐
    │                              │
    │                              ▼
tgt token ids               Cross Attention K,V
    │
    ▼
Embedding + Position
    │
    ▼
┌──────────────────────────────┐
│ Decoder Layer × N            │
│                              │
│ Masked Self-Attention        │
│          ↓                   │
│      Add & Norm              │
│          ↓                   │
│ Cross-Attention              │◄── Encoder memory
│          ↓                   │
│      Add & Norm              │
│          ↓                   │
│ Feed-Forward Network         │
│          ↓                   │
│      Add & Norm              │
└──────────────────────────────┘
    │
    ▼
Linear
    │
    ▼
Vocabulary logits
```

---

## 建议源码阅读顺序

### 1. Scaled Dot-Product Attention

阅读：

```python
scaled_dot_product_attention(...)
```

对应：

```text
Q @ K^T
   ↓
/ sqrt(d_k)
   ↓
Mask
   ↓
Softmax
   ↓
× V
```

---

### 2. Multi-Head Attention

阅读：

```python
class MultiHeadAttention
```

重点：

```text
Q ── Wq ── split heads ─┐
K ── Wk ── split heads ─┼─ Attention ─ Concat ─ Wo
V ── Wv ── split heads ─┘
```

---

### 3. EncoderLayer

阅读：

```python
class EncoderLayer
```

对应：

```text
x
│
├──────────────┐
▼              │
Self Attention │
│              │
Dropout        │
│              │
+ ◄────────────┘
│
LayerNorm
│
├──────────────┐
▼              │
FFN            │
│              │
Dropout        │
│              │
+ ◄────────────┘
│
LayerNorm
```

本项目采用原论文的 **Post-LN** 顺序。

---

### 4. DecoderLayer

阅读：

```python
class DecoderLayer
```

内部顺序：

```text
Masked Self-Attention
        ↓
Add & Norm
        ↓
Cross-Attention
        ↓
Add & Norm
        ↓
FFN
        ↓
Add & Norm
```

---

### 5. Transformer.forward

最后阅读：

```python
Transformer.forward(...)
```

理解完整：

```text
src
 ↓
Encoder
 ↓
Memory
 ↓
Decoder ← tgt
 ↓
Linear
 ↓
logits
```

---

## Mask 约定

本项目统一规定：

```text
True = masked
False = allowed
```

### Causal Mask

例如长度 4：

```text
F T T T
F F T T
F F F T
F F F F
```

保证位置 `i` 看不到未来位置。

### Padding Mask

```text
[B, sequence_length]
```

PAD token 位置为 `True`。

---

## 和现代 Transformer 的区别

本实现是为了忠实理解 2017 Transformer，因此没有加入：

- RoPE
- RMSNorm
- SwiGLU
- FlashAttention
- Grouped-Query Attention
- Multi-Query Attention
- KV Cache
- Pre-LN
- ALiBi
- Mixture-of-Experts

这些属于后续架构演化。

---

## 推荐对照阅读

论文：

Vaswani et al., 2017  
**Attention Is All You Need**  
arXiv:1706.03762

PyTorch 中也提供：

```python
torch.nn.Transformer
torch.nn.TransformerEncoder
torch.nn.TransformerDecoder
torch.nn.MultiheadAttention
```

其中官方文档将这些模块定位为原始 Transformer 架构的参考实现。
