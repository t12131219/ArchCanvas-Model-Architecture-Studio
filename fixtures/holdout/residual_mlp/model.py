"""Unseen residual forecaster used only for generic-recovery holdout tests."""

from torch import nn


class CrossBlendRegressor(nn.Module):
    def __init__(self, d_model: int = 32, forecast_size: int = 6):
        super().__init__()
        self.signal_projection = nn.Linear(d_model, d_model)
        self.context_projection = nn.Linear(d_model, d_model)
        self.activation = nn.GELU()
        self.output_projection = nn.Linear(d_model, d_model)
        self.normalization = nn.LayerNorm(d_model)
        self.forecast_head = nn.Linear(d_model, forecast_size)

    def forward(self, signal, context):
        signal_features = self.signal_projection(signal)
        context_features = self.context_projection(context)
        blended = signal_features + context_features
        activated = self.activation(blended)
        projected = self.output_projection(activated)
        residual = signal + projected
        normalized = self.normalization(residual)
        forecast = self.forecast_head(normalized)
        return forecast
