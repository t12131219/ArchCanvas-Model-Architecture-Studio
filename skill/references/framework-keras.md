# Keras Adapter

Use `--framework keras` for Keras Python source. The adapter statically reads subclassed `Model.call`
methods and Functional builder dataflow without importing TensorFlow or Keras. Explicit assignments,
layer calls, merges, inputs, outputs, source spans, and configured shapes enter Exact IR.

With the optional Keras runtime installed, `trace` executes Functional or subclassed models in the
isolated worker, observes layer calls, normalizes tensor leaves, freezes the seed, and requires two
matching replay digests. The receipt names the active Keras backend; backend-specific behavior does
not inherit another backend's verification status.

Exact config values, registered-layer constructor literals, and Functional inline constructor
arguments can use parameter transactions. Registered `layers.Activation` replacement and exact
single-consumer subclass `LayerNormalization` insertion are bounded structural lowerings. Dynamic
layer construction, custom `train_step`, and ambiguous Functional rewrites remain unsupported and
must produce a capability gap or AgentProposal.
