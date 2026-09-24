# Keras Adapter

Use `--framework keras` for Keras Python source. The adapter statically reads subclassed `Model.call`
methods and Functional builder dataflow without importing TensorFlow or Keras. Explicit assignments,
layer calls, merges, inputs, outputs, source spans, and configured shapes enter Exact IR.

Dynamic layer construction, Python-dependent routing, framework runtime shape inference, runtime
evidence, and source transactions are not supported. Preserve those facts as unresolved rather
than importing the project or assuming standard Keras behavior.
