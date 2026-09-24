# JAX Adapter

Use `--framework jax` for Flax-style `__call__` methods and pure JAX functions. Analysis is static:
JAX, Flax, and Haiku are not imported. Explicit functional dataflow, merges, inputs, outputs, and
configured shapes enter Exact IR.

Framework-lowered control flow, `scan` bodies, implicit parameter-tree sharing, runtime evidence,
and source transactions are not supported. Keep unproven sharing or dynamic topology unresolved.
