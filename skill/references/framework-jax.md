# JAX Adapter

Use `--framework jax` for Flax-style `__call__` methods and pure JAX functions. Analysis is static:
JAX, Flax, and Haiku are not imported. Explicit functional dataflow, merges, inputs, outputs, and
configured shapes enter Exact IR.

With the optional JAX/Flax runtime installed, `trace` records JAXPR/eval-shape observations,
platform, deterministic PRNG initialization, and params/state digests. Pure functions and Flax
Modules use the same normalized runtime receipt without pretending to expose PyTorch hooks.

Config values and exact Flax Module fields support parameter transactions. Explicit
`nn.gelu/relu/silu` assignments support a bounded pure-function activation replacement. Unproven
edits inside `jit`, `vmap`, or `scan`, implicit parameter-tree sharing, checkpoint value mutation,
and ambiguous state collection changes remain unsupported.
