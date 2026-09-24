"""JAX scan fixture used to preserve transformed-function provenance."""

import jax
import jax.numpy as jnp


def recurrent_scan(signal):
    def step(carry, item):
        next_carry = jnp.tanh(carry + item)
        return next_carry, next_carry

    initial = jnp.zeros_like(signal[0])
    scanned = jax.lax.scan(step, initial, signal)
    outputs = scanned[1]
    return outputs
