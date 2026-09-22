from __future__ import annotations

from pathlib import Path

from archcanvas_core.semantic_validation import validate_architecture_semantics
from archcanvas_pytorch.static import PyTorchProjectScanner, PyTorchProjectStaticAdapter


def test_project_scanner_reports_entrypoints_and_unparseable_sources(tmp_path: Path) -> None:
    (tmp_path / "model.py").write_text(
        "from torch import nn\n\n"
        "class Model(nn.Module):\n"
        "    def __init__(self):\n"
        "        super().__init__()\n"
        "        self.linear = nn.Linear(2, 1)\n"
        "    def forward(self, x):\n"
        "        return self.linear(x)\n",
        encoding="utf-8",
    )
    (tmp_path / "broken.py").write_text("def broken(:\n", encoding="utf-8")
    (tmp_path / ".venv").mkdir()
    (tmp_path / ".venv" / "ignored.py").write_text("def broken(:\n", encoding="utf-8")

    report = PyTorchProjectScanner().scan(tmp_path)

    assert report.python_files_scanned == 1
    assert [(item.relative_file, item.model_class) for item in report.entrypoints] == [
        ("model.py", "Model")
    ]
    assert [(item.relative_file, item.code) for item in report.issues] == [
        ("broken.py", "UNPARSEABLE_SOURCE")
    ]


def test_project_scanner_reports_oversized_file_without_reading_it(tmp_path: Path) -> None:
    (tmp_path / "large.py").write_text("# generated\n" * 10, encoding="utf-8")
    report = PyTorchProjectScanner(max_file_bytes=10).scan(tmp_path)
    assert report.python_files_scanned == 0
    assert [(item.relative_file, item.code) for item in report.issues] == [
        ("large.py", "FILE_TOO_LARGE")
    ]


def test_project_scanner_resolves_direct_local_module_import_for_selected_entrypoint(
    tmp_path: Path,
) -> None:
    layers = tmp_path / "layers"
    layers.mkdir()
    (layers / "backbone.py").write_text(
        "from torch import nn\n\n"
        "class Backbone(nn.Module):\n"
        "    def __init__(self):\n"
        "        super().__init__()\n"
        "    def forward(self, x):\n"
        "        return x\n",
        encoding="utf-8",
    )
    (tmp_path / "model.py").write_text(
        "from torch import nn\n"
        "from layers.backbone import Backbone as LocalBackbone\n\n"
        "class Model(nn.Module):\n"
        "    def __init__(self):\n"
        "        super().__init__()\n"
        "        self.backbone = LocalBackbone()\n"
        "    def forward(self, x):\n"
        "        return self.backbone(x)\n",
        encoding="utf-8",
    )

    resolution = PyTorchProjectScanner().build_symbol_table(tmp_path).resolve_entrypoint(
        "model.py:Model"
    )

    assert [(item.local_name, item.target_relative_file, item.target_class_name) for item in resolution.local_module_bindings] == [
        ("LocalBackbone", "layers/backbone.py", "Backbone")
    ]
    assert resolution.issues == []


def test_project_scanner_resolves_the_approved_root_package_name_as_local(tmp_path: Path) -> None:
    root = tmp_path / "projectpkg"
    root.mkdir()
    (root / "layers.py").write_text(
        "from torch import nn\n\n"
        "class Backbone(nn.Module):\n"
        "    def forward(self, x):\n"
        "        return x\n",
        encoding="utf-8",
    )
    (root / "model.py").write_text(
        "from torch import nn\n"
        "from projectpkg.layers import Backbone\n\n"
        "class Model(nn.Module):\n"
        "    def __init__(self):\n"
        "        super().__init__()\n"
        "        self.backbone = Backbone()\n"
        "    def forward(self, x):\n"
        "        return self.backbone(x)\n",
        encoding="utf-8",
    )

    resolution = PyTorchProjectScanner().build_symbol_table(root).resolve_entrypoint("model.py:Model")

    assert [(item.local_name, item.target_relative_file, item.target_class_name) for item in resolution.local_module_bindings] == [
        ("Backbone", "layers.py", "Backbone")
    ]


def test_project_scanner_reports_unresolved_relative_import_for_selected_entrypoint(tmp_path: Path) -> None:
    (tmp_path / "model.py").write_text(
        "from torch import nn\n"
        "from .missing import Missing\n\n"
        "class Model(nn.Module):\n"
        "    def forward(self, x):\n"
        "        return x\n",
        encoding="utf-8",
    )
    resolution = PyTorchProjectScanner().build_symbol_table(tmp_path).resolve_entrypoint(
        "model.py:Model"
    )
    assert [(item.code, item.message) for item in resolution.issues] == [
        ("UNRESOLVED_LOCAL_IMPORT", "missing")
    ]


def test_project_static_adapter_models_branch_free_direct_local_constructor_call(tmp_path: Path) -> None:
    layers = tmp_path / "layers"
    layers.mkdir()
    (layers / "backbone.py").write_text(
        "from torch import nn\n\n"
        "class Backbone(nn.Module):\n"
        "    def __init__(self, width):\n"
        "        super().__init__()\n"
        "        self.proj = nn.Linear(width, width)\n"
        "    def forward(self, x):\n"
        "        return self.proj(x)\n",
        encoding="utf-8",
    )
    (tmp_path / "model.py").write_text(
        "from torch import nn\n"
        "from layers.backbone import Backbone as LocalBackbone\n\n"
        "class Model(nn.Module):\n"
        "    def __init__(self, width):\n"
        "        super().__init__()\n"
        "        self.backbone = LocalBackbone(width)\n"
        "    def forward(self, x):\n"
        "        return self.backbone(x)\n",
        encoding="utf-8",
    )

    identity, ir = PyTorchProjectStaticAdapter().analyze(
        tmp_path,
        project_id="project:cross-file",
        entrypoint="model.py:Model",
    )

    assert validate_architecture_semantics(ir, identity) == []
    assert identity.file_revisions.keys() == {"layers/backbone.py", "model.py"}
    assert [node.node_id for node in ir.nodes] == [
        "node:input",
        "node:model.backbone",
        "node:output",
    ]
    backbone = ir.node("node:model.backbone")
    assert backbone.op_type == "local:layers/backbone.py:Backbone"
    assert backbone.source_anchor_ids == [
        "anchor:model.backbone.constructor",
        "anchor:local.layers.backbone.backbone.class",
    ]
    target_anchor = next(
        anchor
        for anchor in identity.anchors
        if anchor.anchor_id == "anchor:local.layers.backbone.backbone.class"
    )
    assert target_anchor.relative_file == "layers/backbone.py"
    assert target_anchor.symbol_path == "Backbone"
    assert target_anchor.kind.value == "class"
    assert ir.node("node:model.backbone").identity_id in {
        identity_item.identity_id
        for identity_item in identity.identities
        if target_anchor.anchor_id in identity_item.anchor_ids
    }
    assert [(edge.source_node_id, edge.target_node_id) for edge in ir.edges] == [
        ("node:model.backbone", "node:output"),
        ("node:input", "node:model.backbone"),
    ]
    assert ir.metadata["direct_local_binding_count"] == 1


def test_project_static_adapter_fails_closed_for_conditional_local_constructor_call(
    tmp_path: Path,
) -> None:
    (tmp_path / "backbone.py").write_text(
        "from torch import nn\n\n"
        "class Backbone(nn.Module):\n"
        "    def forward(self, x):\n"
        "        return x\n",
        encoding="utf-8",
    )
    (tmp_path / "model.py").write_text(
        "from torch import nn\n"
        "from backbone import Backbone\n\n"
        "class Model(nn.Module):\n"
        "    def __init__(self, enabled):\n"
        "        super().__init__()\n"
        "        if enabled:\n"
        "            self.backbone = Backbone()\n"
        "    def forward(self, x):\n"
        "        return x\n",
        encoding="utf-8",
    )

    identity, ir = PyTorchProjectStaticAdapter().analyze(
        tmp_path,
        project_id="project:conditional-cross-file",
        entrypoint="model.py:Model",
    )

    assert validate_architecture_semantics(ir, identity) == []
    assert [node.node_id for node in ir.nodes] == ["node:input", "node:output"]
    assert [(item.code, item.blocking) for item in ir.unresolved] == [
        ("DYNAMIC_CONSTRUCTOR_CONTROL_FLOW", False)
    ]


def test_project_static_adapter_records_bounded_transitive_local_call_evidence(
    tmp_path: Path,
) -> None:
    (tmp_path / "stem.py").write_text(
        "from torch import nn\n\n"
        "class Stem(nn.Module):\n"
        "    def __init__(self):\n"
        "        super().__init__()\n"
        "        self.proj = nn.Linear(2, 2)\n"
        "    def forward(self, x):\n"
        "        return self.proj(x)\n",
        encoding="utf-8",
    )
    (tmp_path / "backbone.py").write_text(
        "from torch import nn\n"
        "from stem import Stem\n\n"
        "class Backbone(nn.Module):\n"
        "    def __init__(self):\n"
        "        super().__init__()\n"
        "        self.stem = Stem()\n"
        "    def forward(self, x):\n"
        "        return self.stem(x)\n",
        encoding="utf-8",
    )
    (tmp_path / "model.py").write_text(
        "from torch import nn\n"
        "from backbone import Backbone\n\n"
        "class Model(nn.Module):\n"
        "    def __init__(self):\n"
        "        super().__init__()\n"
        "        self.backbone = Backbone()\n"
        "    def forward(self, x):\n"
        "        return self.backbone(x)\n",
        encoding="utf-8",
    )

    identity, ir = PyTorchProjectStaticAdapter().analyze(
        tmp_path,
        project_id="project:transitive-evidence",
        entrypoint="model.py:Model",
    )

    assert validate_architecture_semantics(ir, identity) == []
    assert identity.file_revisions.keys() == {"backbone.py", "model.py", "stem.py"}
    assert ir.metadata["transitive_local_call_evidence"] == [
        {
            "depth": 1,
            "from_entrypoint": "backbone.py:Backbone",
            "call_node_id": "node:backbone.stem",
            "call_anchor_ids": ["anchor:backbone.stem.constructor"],
            "target_entrypoint": "stem.py:Stem",
            "target_class_anchor_id": "anchor:local.stem.stem.class",
            "traversal_status": "expanded",
        }
    ]
    assert {anchor.anchor_id for anchor in identity.anchors} >= {
        "anchor:backbone.stem.constructor",
        "anchor:local.stem.stem.class",
    }
    assert [node.node_id for node in ir.nodes] == [
        "node:input",
        "node:model.backbone",
        "node:output",
    ]
    _, limited_ir = PyTorchProjectStaticAdapter(
        max_transitive_evidence_depth=1
    ).analyze(
        tmp_path,
        project_id="project:transitive-evidence-limited",
        entrypoint="model.py:Model",
    )
    assert limited_ir.metadata["transitive_local_call_evidence"][0]["traversal_status"] == (
        "depth_limit"
    )
