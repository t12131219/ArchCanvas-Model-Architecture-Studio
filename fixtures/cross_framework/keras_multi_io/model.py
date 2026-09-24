"""Keras Functional multi-input/output fixture with an explicitly shared layer."""

from keras import Input
from keras import layers


def build_multi_io():
    signal = Input(shape=(8,), name="signal")
    context = Input(shape=(8,), name="context")
    shared_projection = layers.Dense(8, name="shared_projection")
    signal_features = shared_projection(signal)
    context_features = shared_projection(context)
    merged = layers.Add(name="merged")([signal_features, context_features])
    prediction = layers.Dense(4, name="prediction")(merged)
    auxiliary = layers.Dense(2, name="auxiliary")(signal_features)
    return {"prediction": prediction, "auxiliary": auxiliary}
