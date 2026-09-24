"""Static fixture. Analysis must not import Keras."""

from keras import layers
from keras import Model


class TemporalGate(Model):
    def __init__(self, width=16):
        super().__init__()
        self.input_projection = layers.Dense(width)
        self.gate_projection = layers.Dense(width)
        self.normalization = layers.LayerNormalization()
        self.output_projection = layers.Dense(width)

    def call(self, signal, context):
        projected = self.input_projection(signal)
        gate = self.gate_projection(context)
        gated = projected * gate
        residual = signal + gated
        normalized = self.normalization(residual)
        output = self.output_projection(normalized)
        return output
