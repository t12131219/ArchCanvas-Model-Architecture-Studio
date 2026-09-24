from __future__ import annotations

import copy
import hashlib
from pathlib import Path
from typing import Any

from .onnx_external import build_artifact_set
from .runtime_common import matched_nodes, numpy_input


def _record(value: Any, provider: str) -> dict[str, Any]:
    return {
        "shape": list(value.shape),
        "dtype": str(value.dtype),
        "device": provider,
        "requires_grad": None,
        "trainable": False,
    }


def execute(request: dict[str, Any]) -> dict[str, Any]:
    import numpy as np
    import onnx
    import onnxruntime as ort

    spec = request["input_spec"]
    available = ort.get_available_providers()
    selected = spec.get("selected_target") or "CPUExecutionProvider"
    if selected in {"cpu", "auto"}:
        selected = "CPUExecutionProvider"
    if selected not in available:
        raise RuntimeError(
            f"ONNX Runtime provider {selected!r} is unavailable; available providers: {available}"
        )
    project = Path(request["project_root"]).resolve()
    model_path = (project / Path(request["entrypoint"])).resolve()
    if not model_path.is_relative_to(project) or not model_path.is_file():
        raise RuntimeError("ONNX runtime entrypoint is outside the project or missing")
    stored_model = onnx.load(model_path, load_external_data=False)
    artifact_set = build_artifact_set(stored_model, model_path, project)
    model = onnx.load(model_path, load_external_data=True)
    inferred = onnx.shape_inference.infer_shapes(model)
    instrumented = copy.deepcopy(inferred)
    existing_outputs = {item.name for item in instrumented.graph.output}
    type_by_name = {
        item.name: item
        for item in [*instrumented.graph.input, *instrumented.graph.value_info, *instrumented.graph.output]
    }
    intermediate_names: list[str] = []
    for node in instrumented.graph.node:
        for name in node.output:
            if name and name not in existing_outputs and name in type_by_name:
                instrumented.graph.output.append(copy.deepcopy(type_by_name[name]))
                existing_outputs.add(name)
                intermediate_names.append(name)
    options = ort.SessionOptions()
    options.intra_op_num_threads = 1
    options.inter_op_num_threads = 1
    session = ort.InferenceSession(
        instrumented.SerializeToString(),
        sess_options=options,
        providers=[selected],
        provider_options=[spec.get("provider_options", {}).get(selected, {})],
    )
    feeds = {
        item["name"]: numpy_input(item, np, spec["seed"] + index)
        for index, item in enumerate(spec["inputs"])
    }
    required_inputs = {item.name for item in session.get_inputs()}
    if set(feeds) != required_inputs:
        raise RuntimeError(
            f"runtime inputs do not match ONNX graph inputs: expected {sorted(required_inputs)}, "
            f"received {sorted(feeds)}"
        )
    output_names = [item.name for item in session.get_outputs()]
    values = session.run(output_names, feeds)
    value_map = dict(zip(output_names, values, strict=True))
    value_map.update(feeds)
    observations: list[dict[str, Any]] = []
    for index, node in enumerate(instrumented.graph.node):
        outputs = [value_map[name] for name in node.output if name in value_map]
        inputs = [value_map[name] for name in node.input if name in value_map]
        subject = node.name or f"{node.op_type}.{index}"
        observations.append(
            {
                "module_path": subject,
                "module_type": node.op_type,
                "input_tensors": [_record(value, selected) for value in inputs],
                "output_tensors": [_record(value, selected) for value in outputs],
                "matched_node_ids": matched_nodes(
                    request, subject, node.op_type, *[name for name in node.output if name]
                ),
                "attributes": {"domain": node.domain or "ai.onnx"},
            }
        )
    graph_outputs = [value_map[item.name] for item in inferred.graph.output]
    return {
        "observations": observations,
        "output_tensors": [_record(value, selected) for value in graph_outputs],
        "checkpoint_digest": artifact_set.set_digest,
        "environment": {
            "python_version": request["runtime_python_version"],
            "platform": request["runtime_platform"],
            "adapter_id": "runtime:onnxruntime-v1",
            "framework": "onnx",
            "framework_version": onnx.__version__,
            "backend": "onnxruntime",
            "backend_version": ort.__version__,
            "selected_target": selected,
            "available_targets": [{"kind": "provider", "id": item} for item in available],
            "observation_mechanism": "onnx-graph-outputs-v1",
            "runtime_context": {
                "form": "modelproto",
                "artifact_set_id": artifact_set.artifact_set_id,
                "artifact_members": [entry.logical_path for entry in artifact_set.entries],
                "provider_options_digest": hashlib.sha256(
                    repr(sorted(spec.get("provider_options", {}).get(selected, {}).items())).encode()
                ).hexdigest(),
                "instrumented_output_count": len(intermediate_names),
                "instrumentation_persisted": False,
                "opsets": {
                    (item.domain or "ai.onnx"): item.version for item in model.opset_import
                },
                "custom_domains": sorted(
                    {node.domain for node in model.graph.node if node.domain not in {"", "ai.onnx"}}
                ),
            },
        },
        "limitations": [
            "Only values with inferred ONNX type information are temporarily exposed as outputs."
        ] if intermediate_names else ["The graph exposed no typed intermediate values."],
    }
