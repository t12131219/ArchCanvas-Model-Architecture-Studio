# ONNX Adapter

Use `--framework onnx --entry model.onnx` for a project-relative ModelProto. The adapter uses the
official ONNX parser and shape inference without executing the graph or loading external tensor
data. Graph inputs, initializers, operators, values, fan-out, and outputs become canonical facts.

ONNX runtime evidence and source transactions are unsupported. An invalid or open graph is a hard
analysis error; do not repair missing producers or invent model semantics from operator names.
