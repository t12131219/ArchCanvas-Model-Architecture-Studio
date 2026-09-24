"""Pure JAX-style function fixture. Analysis must not import JAX."""

import jax.numpy as jnp


def residual_projection(signal, weight, bias):
    projected = jnp.dot(signal, weight)
    shifted = projected + bias
    activated = jnp.tanh(shifted)
    output = signal + activated
    return output
