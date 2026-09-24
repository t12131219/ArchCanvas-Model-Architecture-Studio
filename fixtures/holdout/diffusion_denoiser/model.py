"""Unseen timestep-conditioned denoiser used for generic recovery acceptance."""

from torch import nn


class TimestepDenoiser(nn.Module):
    def __init__(self, channels: int = 16):
        super().__init__()
        self.noise_projection = nn.Linear(channels, channels)
        self.time_projection = nn.Linear(channels, channels)
        self.activation = nn.SiLU()
        self.clean_projection = nn.Linear(channels, channels)

    def forward(self, noisy, timestep):
        signal = self.noise_projection(noisy)
        condition = self.time_projection(timestep)
        conditioned = signal + condition
        hidden = self.activation(conditioned)
        estimate = self.clean_projection(hidden)
        return estimate
