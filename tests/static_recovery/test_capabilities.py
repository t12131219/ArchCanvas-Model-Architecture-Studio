from __future__ import annotations

import json

from archcanvas_pytorch import static_capability_report


def test_static_capability_report_is_machine_readable_and_bounded() -> None:
    report = static_capability_report()
    payload = report.as_dict()
    assert json.loads(json.dumps(payload)) == payload
    assert "torch.cat and torch.stack with known list/tuple inputs" in payload["supported"]
    assert "read-only project entrypoint discovery" in payload["supported"]
    assert "dynamic if control flow" in payload["unresolved"]
    assert "cross-file custom module topology" in payload["excluded"]
    assert "runtime shape inference" in payload["excluded"]
