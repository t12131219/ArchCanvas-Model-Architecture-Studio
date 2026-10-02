from __future__ import annotations

from collections.abc import Callable
from pathlib import Path

import pytest
from pydantic import ValidationError

from archcanvas_core.architecture_v2 import (
    EXACT_IR_DIGEST_DOMAIN,
    SEMANTIC_GRAPH_DIGEST_DOMAIN,
    ExactArchitectureIRV2,
    PythonSemanticGraph,
    exact_ir_payload,
    semantic_graph_payload,
)
from archcanvas_core.digest_protocol import domain_digest
from archcanvas_python import analyze_project_v2

ROOT = Path(__file__).resolve().parents[2]
FIXTURE = ROOT / "tests" / "fixtures" / "frontend_v2" / "transformer_classic"


def _graph_values(graph: PythonSemanticGraph) -> dict[str, object]:
    return {
        name: getattr(graph, name)
        for name in PythonSemanticGraph.model_fields
        if name != "semantic_graph_digest"
    }


def _invalid_graph(
    graph: PythonSemanticGraph,
    mutate: Callable[[dict[str, object]], None],
) -> dict[str, object]:
    values = _graph_values(graph)
    mutate(values)
    prototype = PythonSemanticGraph.model_construct(
        semantic_graph_digest="0" * 64,
        **values,
    )
    return {
        **values,
        "semantic_graph_digest": domain_digest(
            SEMANTIC_GRAPH_DIGEST_DOMAIN,
            semantic_graph_payload(prototype),
        ),
    }


@pytest.mark.parametrize(
    "mutate",
    [
        lambda values: values.update(
            parameter_groups=[
                values["parameter_groups"][0].model_copy(  # type: ignore[index,union-attr]
                    update={"call_ids": ["call:missing"]}
                ),
                *values["parameter_groups"][1:],  # type: ignore[index]
            ]
        ),
        lambda values: values.update(
            repeats=[
                values["repeats"][0].model_copy(  # type: ignore[index,union-attr]
                    update={"body_call_ids": ["call:missing"]}
                ),
                *values["repeats"][1:],  # type: ignore[index]
            ]
        ),
        lambda values: values.update(
            pattern_bindings=[
                values["pattern_bindings"][0].model_copy(  # type: ignore[index,union-attr]
                    update={"subject_ids": ["call:missing"]}
                )
            ]
        ),
        lambda values: values.update(
            pattern_bindings=[
                values["pattern_bindings"][0].model_copy(  # type: ignore[index,union-attr]
                    update={"slot_bindings": {"unknown": ["value:missing"]}}
                )
            ]
        ),
        lambda values: values.update(graph_input_value_ids=["value:missing"]),
        lambda values: values.update(graph_output_value_ids=["value:missing"]),
    ],
    ids=[
        "parameter-call",
        "repeat-call",
        "pattern-subject",
        "pattern-slot",
        "graph-input",
        "graph-output",
    ],
)
def test_semantic_graph_rejects_dangling_relationships(
    tmp_path: Path,
    mutate: Callable[[dict[str, object]], None],
) -> None:
    bundle = analyze_project_v2(
        FIXTURE,
        "model:Transformer",
        "inference",
        "eval",
        tmp_path / "workspace",
    )

    with pytest.raises(ValidationError, match="unknown IDs"):
        PythonSemanticGraph.model_validate(_invalid_graph(bundle.semantic_graph, mutate))


def test_exact_ir_rejects_dangling_relationships(tmp_path: Path) -> None:
    bundle = analyze_project_v2(
        FIXTURE,
        "model:Transformer",
        "inference",
        "eval",
        tmp_path / "workspace",
    )
    ir = bundle.exact_ir
    values = {
        name: getattr(ir, name)
        for name in ExactArchitectureIRV2.model_fields
        if name != "exact_ir_digest"
    }
    values["repeats"] = [
        ir.repeats[0].model_copy(update={"container_instance_id": "instance:missing"}),
        *ir.repeats[1:],
    ]
    prototype = ExactArchitectureIRV2.model_construct(exact_ir_digest="0" * 64, **values)
    values["exact_ir_digest"] = domain_digest(EXACT_IR_DIGEST_DOMAIN, exact_ir_payload(prototype))

    with pytest.raises(ValidationError, match="unknown IDs"):
        ExactArchitectureIRV2.model_validate(values)
