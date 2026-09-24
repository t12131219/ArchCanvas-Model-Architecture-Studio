"""Flax-style fixture. Analysis must not import JAX or Flax."""

from flax import linen as nn
import jax.numpy as jnp


class ResidualMixer(nn.Module):
    width: int = 16

    @nn.compact
    def __call__(self, signal, context):
        signal_projection = nn.Dense(self.width)(signal)
        context_projection = nn.Dense(self.width)(context)
        mixed = signal_projection + context_projection
        activated = nn.gelu(mixed)
        output = nn.Dense(self.width)(activated)
        residual = jnp.add(signal, output)
        return residual
