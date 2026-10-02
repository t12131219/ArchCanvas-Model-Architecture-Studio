import type { ChangeSet, Text } from "@codemirror/state";

export interface EditorPoint {
  row: number;
  column: number;
}

export interface PythonSyntaxEdit {
  startIndex: number;
  oldEndIndex: number;
  newEndIndex: number;
  startPosition: EditorPoint;
  oldEndPosition: EditorPoint;
  newEndPosition: EditorPoint;
}

export interface EditorLocalDiagnostic {
  from: number;
  to: number;
  severity: "error";
  message: string;
  source: "editor-local";
}

export interface EditorLocalFold {
  from: number;
  to: number;
  line: number;
}

export interface EditorLocalSymbol {
  kind: "class" | "function" | "async-function";
  name: string;
  from: number;
  to: number;
  line: number;
}

export interface PythonSyntaxParseRequest {
  type: "parse-python";
  requestId: string;
  text: string;
  previousLength: number | null;
  edits: PythonSyntaxEdit[];
}

export interface PythonSyntaxSuccess {
  type: "python-syntax-complete";
  requestId: string;
  source: "editor-local";
  parseMode: "full" | "incremental";
  durationMs: number;
  diagnostics: EditorLocalDiagnostic[];
  folds: EditorLocalFold[];
  symbols: EditorLocalSymbol[];
}

export interface PythonSyntaxFailure {
  type: "python-syntax-failed";
  requestId: string;
  message: string;
}

export type PythonSyntaxWorkerRequest = PythonSyntaxParseRequest;
export type PythonSyntaxWorkerResponse = PythonSyntaxSuccess | PythonSyntaxFailure;

function pointAt(document: Text, position: number): EditorPoint {
  const line = document.lineAt(position);
  return { row: line.number - 1, column: position - line.from };
}

function advancePoint(start: EditorPoint, text: string): EditorPoint {
  const lines = text.split("\n");
  return lines.length === 1
    ? { row: start.row, column: start.column + text.length }
    : { row: start.row + lines.length - 1, column: lines.at(-1)!.length };
}

/** Convert one atomic CodeMirror ChangeSet into the sequential edits expected by Tree.edit(). */
export function pythonSyntaxEdits(
  changes: ChangeSet,
  oldDocument: Text,
  newDocument: Text,
): PythonSyntaxEdit[] {
  const edits: PythonSyntaxEdit[] = [];
  changes.iterChanges((fromA, toA, fromB, toB) => {
    const startPosition = pointAt(newDocument, fromB);
    edits.push({
      startIndex: fromB,
      oldEndIndex: fromB + (toA - fromA),
      newEndIndex: toB,
      startPosition,
      oldEndPosition: advancePoint(startPosition, oldDocument.sliceString(fromA, toA)),
      newEndPosition: pointAt(newDocument, toB),
    });
  });
  return edits;
}
