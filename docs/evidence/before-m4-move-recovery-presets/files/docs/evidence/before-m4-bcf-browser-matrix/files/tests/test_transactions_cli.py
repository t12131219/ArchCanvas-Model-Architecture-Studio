"""CLI transport cannot broaden the explicitly bound source project or approval."""

import contextlib
import io
import json
import tempfile
import unittest
from pathlib import Path

from archcanvas_cli.__main__ import main
from archcanvas_python import analyze_project


SOURCE = """from torch import nn
class Model(nn.Module):
    def __init__(self):
        self.drop = nn.Dropout(0.1)
    def forward(self, x):
        return self.drop(x)
"""


class TransactionCliTests(unittest.TestCase):
    def setUp(self):
        self.temporary = tempfile.TemporaryDirectory(prefix="archcanvas-cli-transaction-", dir="/tmp")
        self.base = Path(self.temporary.name)
        self.root = self.base / "project"
        self.root.mkdir()
        self.path = self.root / "model.py"
        self.path.write_text(SOURCE)
        self.store = self.base / "private-store"

    def tearDown(self):
        self.temporary.cleanup()

    def invoke(self, arguments):
        stdout, stderr = io.StringIO(), io.StringIO()
        with contextlib.redirect_stdout(stdout), contextlib.redirect_stderr(stderr):
            status = main(arguments)
        text = stdout.getvalue() or stderr.getvalue()
        return status, json.loads(text)

    def patch_args(self, action, *, root=None):
        return ["patch", action, "--root", str(root or self.root), "--entry", "model:Model", "--store", str(self.store)]

    def prepare(self):
        architecture = analyze_project(self.root, "model:Model")
        node = next(node for node in architecture["nodes"] if node["kind"] == "Dropout")
        status, receipt = self.invoke(self.patch_args("prepare") + ["--node", node["id"], "--parameter", "p", "--value", "0.2", "--base-source-digest", architecture["sourceDigest"]])
        self.assertEqual(status, 0, receipt)
        return receipt

    def test_cli_exact_review_approval_and_commit(self):
        prepared = self.prepare()
        self.assertEqual(self.path.read_text(), SOURCE)
        review_args = self.patch_args("review") + ["--transaction", prepared["id"]]
        status, reviewed = self.invoke(review_args)
        self.assertEqual(status, 0)
        self.assertEqual(reviewed["reviewDigest"], prepared["reviewDigest"])
        self.assertIn("-        self.drop = nn.Dropout(0.1)", reviewed["diff"])
        status, failed = self.invoke(self.patch_args("commit") + ["--transaction", prepared["id"], "--approval-id", "no-human-approval"])
        self.assertEqual(status, 2)
        self.assertIn("approval", failed["error"])
        self.assertEqual(self.path.read_text(), SOURCE)
        status, approved = self.invoke(self.patch_args("approve") + ["--transaction", prepared["id"], "--review-digest", reviewed["reviewDigest"]])
        self.assertEqual(status, 0)
        status, committed = self.invoke(self.patch_args("commit") + ["--transaction", prepared["id"], "--approval-id", approved["approvalId"]])
        self.assertEqual(status, 0)
        self.assertEqual(committed["status"], "Committed")
        self.assertEqual(self.path.read_text(), SOURCE.replace("Dropout(0.1)", "Dropout(0.2)"))

    def test_cli_wrong_root_rejected_before_manager_recovery(self):
        receipt = self.prepare()
        another = self.base / "another-project"
        another.mkdir()
        (another / "model.py").write_text(SOURCE)
        status, rejected = self.invoke(self.patch_args("review", root=another) + ["--transaction", receipt["id"]])
        self.assertEqual(status, 2)
        self.assertIn("another root/entry", rejected["error"])
        self.assertEqual(self.path.read_text(), SOURCE)
        self.assertEqual((another / "model.py").read_text(), SOURCE)

    def test_cli_help_states_exact_approval_and_required_root(self):
        output = io.StringIO()
        with contextlib.redirect_stdout(output), self.assertRaises(SystemExit) as exit_info:
            main(["patch", "approve", "--help"])
        self.assertEqual(exit_info.exception.code, 0)
        text = output.getvalue()
        self.assertIn("--root", text)
        self.assertIn("--entry", text)
        self.assertIn("--review-digest", text)
        self.assertIn("reviewed by the human", " ".join(text.split()))

    def test_cli_source_bom_crlf_uses_raw_byte_binding(self):
        self.path.write_bytes(b"\xef\xbb\xbf" + SOURCE.replace("\n", "\r\n").encode())
        status, cli_analysis = self.invoke(["analyze", "--source", str(self.path), "--entry", "Model"])
        self.assertEqual(status, 0)
        self.assertEqual(cli_analysis["sourceDigest"], analyze_project(self.root, "model:Model")["sourceDigest"])
        self.assertIn("\r\n", cli_analysis["sources"][0]["content"])


if __name__ == "__main__":
    unittest.main()
