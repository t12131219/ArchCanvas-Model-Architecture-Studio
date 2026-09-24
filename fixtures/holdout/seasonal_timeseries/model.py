"""Unseen seasonal/trend forecaster used for generic recovery acceptance."""

from torch import nn


class SeasonalTrendForecaster(nn.Module):
    def __init__(self, d_model: int = 18, horizon: int = 6):
        super().__init__()
        self.trend_projection = nn.Linear(d_model, d_model)
        self.seasonal_projection = nn.Linear(d_model, d_model)
        self.normalization = nn.LayerNorm(d_model)
        self.forecast = nn.Linear(d_model, horizon)

    def forward(self, history, seasonal_context):
        trend = self.trend_projection(history)
        seasonal = self.seasonal_projection(seasonal_context)
        recomposed = trend + seasonal
        normalized = self.normalization(recomposed)
        prediction = self.forecast(normalized)
        return prediction
