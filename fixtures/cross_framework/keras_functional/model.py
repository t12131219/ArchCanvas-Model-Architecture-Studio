"""Keras Functional topology fixture. Analysis must not execute the builder."""

from keras import Input
from keras import layers


def build_network():
    inputs = Input(shape=(12, 8))
    hidden = layers.Dense(16)(inputs)
    activated = layers.Activation("gelu")(hidden)
    outputs = layers.Dense(4)(activated)
    return outputs
