# ONNX Adapter

Use `--framework onnx --entry model.onnx` for a project-relative ModelProto. The adapter uses the
official ONNX parser and shape inference without executing the graph or loading external tensor
data. Graph inputs, initializers, operators, values, fan-out, and outputs become canonical facts.

With ONNX Runtime installed, `trace` selects an explicit Execution Provider, temporarily exposes
typed intermediate values on an in-memory model copy, and requires two matching normalized
replays. Instrumentation never changes the source `.onnx` digest.

ModelProto transactions can change a shape-preserving initializer value, a type-preserving node
attribute, or a bounded standard activation node. They run checker, shape inference, adapter
reanalysis, exact Graph Delta, publication, optional runtime replay, and atomic artifact commit.
External-data mutation is currently rejected because multi-file atomic commit is not yet verified;
custom operators require their provider library and are never rewritten implicitly.
