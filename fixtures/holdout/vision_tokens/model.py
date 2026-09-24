"""Unseen convolution/token hybrid used for generic recovery acceptance."""

from torch import nn


class VisionTokenStem(nn.Module):
    def __init__(self, channels: int = 3, d_model: int = 32, classes: int = 10):
        super().__init__()
        self.patch_projection = nn.Conv2d(channels, d_model, 4, 4)
        self.token_mixer = nn.Linear(d_model, d_model)
        self.activation = nn.GELU()
        self.classifier = nn.Linear(d_model, classes)

    def forward(self, image):
        patches = self.patch_projection(image)
        mixed = self.token_mixer(patches)
        activated = self.activation(mixed)
        logits = self.classifier(activated)
        return logits
