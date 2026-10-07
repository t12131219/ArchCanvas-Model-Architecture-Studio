"""Hand-authored vision holdout used for M4 generalization checks.

This is intentionally independent of the existing transformer/CNN fixtures:
patch projection, token attention and a residual MLP are composed directly in
source, while the unsupported companion class records an opaque boundary.
"""

from torch import nn


class TokenBlock(nn.Module):
    def __init__(self, dim=16, heads=4):
        super().__init__()
        self.norm = nn.LayerNorm(dim)
        self.attention = nn.MultiheadAttention(dim, heads, batch_first=True)
        self.mlp = nn.Sequential(
            nn.Linear(dim, dim * 2),
            nn.GELU(),
            nn.Linear(dim * 2, dim),
        )

    def forward(self, tokens):
        normalized = self.norm(tokens)
        attended, weights = self.attention(normalized, normalized, normalized, need_weights=False)
        tokens = tokens + attended
        return tokens + self.mlp(tokens)


class PatchVisionEncoder(nn.Module):
    """A compact ViT-style encoder with no template-specific graph facts."""

    def __init__(self, dim=16, heads=4, classes=10):
        super().__init__()
        self.patch_projection = nn.Conv2d(3, dim, 4, stride=4)
        self.block = TokenBlock(dim, heads)
        self.classifier = nn.Linear(dim, classes)

    def forward(self, image):
        tokens = self.patch_projection(image)
        tokens = tokens.flatten(2).transpose(1, 2)
        tokens = self.block(tokens)
        pooled = tokens.mean(dim=1)
        return self.classifier(pooled)


class OpaqueTokenMixer(nn.Module):
    """Conv1d is deliberately outside the first public constructor registry."""

    def __init__(self, channels=16):
        super().__init__()
        self.mixer = nn.Conv1d(channels, channels, 3, padding=1)

    def forward(self, tokens):
        return self.mixer(tokens)


class UnsupportedVision(nn.Module):
    """A holdout whose unknown Conv1d operation must remain opaque."""

    def __init__(self, channels=16):
        super().__init__()
        self.mixer = OpaqueTokenMixer(channels)

    def forward(self, tokens):
        return self.mixer(tokens)
