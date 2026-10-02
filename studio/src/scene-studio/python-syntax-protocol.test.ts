import { EditorState } from "@codemirror/state";
import { describe, expect, it } from "vitest";

import { pythonSyntaxEdits } from "./python-syntax-protocol";

describe("python syntax incremental edits", () => {
  it("maps a multiline replacement to Tree.edit coordinates", () => {
    const oldState = EditorState.create({ doc: "def model(x):\n    return x\n" });
    const changes = oldState.changes({ from: 18, to: 26, insert: "value = x\n    return value" });
    const newDocument = changes.apply(oldState.doc);

    expect(pythonSyntaxEdits(changes, oldState.doc, newDocument)).toEqual([{
      startIndex: 18,
      oldEndIndex: 26,
      newEndIndex: 44,
      startPosition: { row: 1, column: 4 },
      oldEndPosition: { row: 1, column: 12 },
      newEndPosition: { row: 2, column: 16 },
    }]);
  });

  it("keeps UTF-16 offsets aligned with CodeMirror and Tree-sitter", () => {
    const oldState = EditorState.create({ doc: "label = '模型'\nvalue = 1\n" });
    const changes = oldState.changes({ from: 9, to: 11, insert: "编码器" });
    const newDocument = changes.apply(oldState.doc);

    expect(pythonSyntaxEdits(changes, oldState.doc, newDocument)[0]).toMatchObject({
      startIndex: 9,
      oldEndIndex: 11,
      newEndIndex: 12,
      startPosition: { row: 0, column: 9 },
      oldEndPosition: { row: 0, column: 11 },
      newEndPosition: { row: 0, column: 12 },
    });
  });

  it("emits sequential coordinates for disjoint atomic changes", () => {
    const oldState = EditorState.create({ doc: "alpha = 1\nbeta = 2\n" });
    const changes = oldState.changes([
      { from: 0, to: 5, insert: "a" },
      { from: 10, to: 14, insert: "second" },
    ]);
    const newDocument = changes.apply(oldState.doc);

    expect(pythonSyntaxEdits(changes, oldState.doc, newDocument)).toEqual([
      expect.objectContaining({ startIndex: 0, oldEndIndex: 5, newEndIndex: 1 }),
      expect.objectContaining({ startIndex: 6, oldEndIndex: 10, newEndIndex: 12 }),
    ]);
  });
});
