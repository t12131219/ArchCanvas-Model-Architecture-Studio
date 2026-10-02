/// <reference lib="webworker" />

import Parser from "web-tree-sitter";
import runtimeWasmUrl from "web-tree-sitter/tree-sitter.wasm?url";
import pythonWasmUrl from "tree-sitter-wasms/out/tree-sitter-python.wasm?url";

import type {
  EditorLocalDiagnostic,
  EditorLocalFold,
  EditorLocalSymbol,
  PythonSyntaxSuccess,
  PythonSyntaxWorkerRequest,
  PythonSyntaxWorkerResponse,
} from "./python-syntax-protocol";

const foldableTypes = new Set([
  "class_definition",
  "function_definition",
  "if_statement",
  "for_statement",
  "while_statement",
  "with_statement",
  "try_statement",
  "match_statement",
]);

let parserPromise: Promise<Parser> | null = null;
let tree: Parser.Tree | null = null;
let currentText = "";
let queue = Promise.resolve();

async function parserInstance(): Promise<Parser> {
  if (!parserPromise) {
    parserPromise = (async () => {
      await Parser.init({ locateFile: () => runtimeWasmUrl });
      const parser = new Parser();
      parser.setLanguage(await Parser.Language.load(pythonWasmUrl));
      return parser;
    })();
  }
  return parserPromise;
}

function syntaxResult(root: Parser.SyntaxNode, text: string) {
  const diagnostics: EditorLocalDiagnostic[] = [];
  const folds: EditorLocalFold[] = [];
  const symbols: EditorLocalSymbol[] = [];
  const seenDiagnostics = new Set<string>();
  const seenFolds = new Set<string>();
  const stack = [root];

  while (stack.length) {
    const node = stack.pop()!;
    const missing = node.isMissing();
    if ((node.type === "ERROR" || missing) && diagnostics.length < 200) {
      const from = Math.min(text.length, node.startIndex);
      const to = Math.min(text.length, Math.max(from, node.endIndex));
      const key = `${from}:${to}:${node.type}:${missing}`;
      if (!seenDiagnostics.has(key)) {
        seenDiagnostics.add(key);
        const excerpt = node.text.replace(/\s+/g, " ").slice(0, 32);
        diagnostics.push({
          from,
          to,
          severity: "error",
          message: missing ? `Missing ${node.type}` : `Syntax error${excerpt ? ` near “${excerpt}”` : ""}`,
          source: "editor-local",
        });
      }
    }

    if (foldableTypes.has(node.type) && node.endPosition.row > node.startPosition.row) {
      const from = text.indexOf("\n", node.startIndex);
      const to = Math.min(text.length, node.endIndex);
      const key = `${from}:${to}`;
      if (from >= 0 && to > from && !seenFolds.has(key)) {
        seenFolds.add(key);
        folds.push({ from, to, line: node.startPosition.row + 1 });
      }
    }

    if (node.type === "class_definition" || node.type === "function_definition") {
      const name = node.childForFieldName("name")?.text;
      if (name) {
        const isAsync = node.parent?.type === "async_statement";
        symbols.push({
          kind: node.type === "class_definition" ? "class" : isAsync ? "async-function" : "function",
          name,
          from: node.startIndex,
          to: node.endIndex,
          line: node.startPosition.row + 1,
        });
      }
    }

    for (let index = node.children.length - 1; index >= 0; index -= 1) stack.push(node.children[index]);
  }

  return {
    diagnostics: diagnostics.sort((left, right) => left.from - right.from || left.to - right.to),
    folds: folds.sort((left, right) => left.from - right.from || left.to - right.to),
    symbols: symbols.sort((left, right) => left.from - right.from || left.name.localeCompare(right.name)),
  };
}

function errorMessage(error: unknown): string {
  return error instanceof Error ? error.message : String(error);
}

async function parse(request: PythonSyntaxWorkerRequest): Promise<void> {
  const startedAt = performance.now();
  try {
    const parser = await parserInstance();
    const canIncrement = tree !== null
      && request.previousLength === currentText.length
      && request.edits.length > 0;
    if (canIncrement) {
      for (const edit of request.edits) tree!.edit(edit);
    } else if (tree) {
      tree.delete();
      tree = null;
    }
    const nextTree = parser.parse(request.text, tree ?? undefined);
    tree?.delete();
    tree = nextTree;
    currentText = request.text;
    const result = syntaxResult(nextTree.rootNode, request.text);
    const response: PythonSyntaxSuccess = {
      type: "python-syntax-complete",
      requestId: request.requestId,
      source: "editor-local",
      parseMode: canIncrement ? "incremental" : "full",
      durationMs: performance.now() - startedAt,
      ...result,
    };
    self.postMessage(response);
  } catch (error) {
    const response: PythonSyntaxWorkerResponse = {
      type: "python-syntax-failed",
      requestId: request.requestId,
      message: errorMessage(error),
    };
    self.postMessage(response);
  }
}

self.onmessage = (event: MessageEvent<PythonSyntaxWorkerRequest>) => {
  if (event.data.type !== "parse-python") return;
  queue = queue.then(() => parse(event.data));
};

export {};
