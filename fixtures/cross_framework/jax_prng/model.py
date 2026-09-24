"""Pure JAX PRNG/static-argument fixture for deterministic replay evidence."""

import jax
import jax.numpy as jnp


def keyed_mask(signal, key, rate=0.25):
    keep = jax.random.bernoulli(key, p=1.0 - rate, shape=signal.shape)
    output = jnp.where(keep, signal, 0.0)
    return output
