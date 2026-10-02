import { defaultKeymap, history, historyKeymap } from "@codemirror/commands";
import { json } from "@codemirror/lang-json";
import { python } from "@codemirror/lang-python";
import { codeFolding, defaultHighlightStyle, foldGutter, foldKeymap, foldService, syntaxHighlighting } from "@codemirror/language";
import { lintGutter, lintKeymap, setDiagnostics } from "@codemirror/lint";
import { EditorState } from "@codemirror/state";
import {
  EditorView,
  highlightActiveLine,
  highlightActiveLineGutter,
  highlightSpecialChars,
  keymap,
  lineNumbers,
} from "@codemirror/view";
import { useEffect, useRef, useState } from "react";

import { createPythonSyntaxService } from "./python-syntax-worker-client";
import { pythonSyntaxEdits, type PythonSyntaxSuccess } from "./python-syntax-protocol";

export interface CodeMirrorEditorProps {
  value: string;
  path: string;
  readOnly: boolean;
  anchorLine?: number | null;
  onChange: (value: string) => void;
}

const editorTheme = EditorView.theme({
  "&": { height: "100%", background: "#202724", color: "#dfe7e2", fontSize: "11px" },
  ".cm-scroller": { overflow: "auto", fontFamily: "ui-monospace, SFMono-Regular, Menlo, Consolas, monospace" },
  ".cm-content": { padding: "8px 0", caretColor: "#dfe7e2" },
  ".cm-gutters": { background: "#252e2a", color: "#82938b", borderRight: "1px solid #3d4a44" },
  ".cm-activeLine, .cm-activeLineGutter": { background: "#34433d" },
  ".cm-selectionBackground, ::selection": { background: "#315b6f !important" },
  "&.cm-focused": { outline: "none" },
});

export function CodeMirrorEditor({ value, path, readOnly, anchorLine, onChange }: CodeMirrorEditorProps) {
  const hostRef = useRef<HTMLDivElement | null>(null);
  const viewRef = useRef<EditorView | null>(null);
  const syntaxRef = useRef<PythonSyntaxSuccess | null>(null);
  const onChangeRef = useRef(onChange);
  const [syntaxStatus, setSyntaxStatus] = useState<"loading" | "ready" | "failed">("loading");
  const [syntaxSnapshot, setSyntaxSnapshot] = useState<PythonSyntaxSuccess | null>(null);
  onChangeRef.current = onChange;

  useEffect(() => {
    const host = hostRef.current;
    if (!host) return;
    const isPython = path.toLowerCase().endsWith(".py");
    const language = path.toLowerCase().endsWith(".json") ? json() : python();
    const syntaxService = isPython ? createPythonSyntaxService() : null;
    let parseSequence = 0;
    let active = true;
    const parseSyntax = (
      text: string,
      previousLength: number | null,
      edits: ReturnType<typeof pythonSyntaxEdits>,
    ) => {
      if (!syntaxService) return;
      const sequence = ++parseSequence;
      setSyntaxStatus("loading");
      void syntaxService.parse({ text, previousLength, edits }).then((result) => {
        if (!active || sequence !== parseSequence) return;
        syntaxRef.current = result;
        setSyntaxSnapshot(result);
        setSyntaxStatus("ready");
        const editor = viewRef.current;
        if (!editor) return;
        const length = editor.state.doc.length;
        editor.dispatch(setDiagnostics(editor.state, result.diagnostics
          .filter((item) => item.from <= length && item.to <= length)
          .map((item) => ({ ...item }))));
      }).catch(() => {
        if (!active || sequence !== parseSequence) return;
        syntaxRef.current = null;
        setSyntaxSnapshot(null);
        setSyntaxStatus("failed");
      });
    };
    const view = new EditorView({
      parent: host,
      state: EditorState.create({
        doc: value,
        extensions: [
          lineNumbers(),
          highlightActiveLineGutter(),
          highlightSpecialChars(),
          history(),
          highlightActiveLine(),
          syntaxHighlighting(defaultHighlightStyle, { fallback: true }),
          keymap.of([...defaultKeymap, ...historyKeymap, ...foldKeymap, ...lintKeymap]),
          language,
          ...(isPython ? [
            codeFolding(),
            foldGutter(),
            lintGutter(),
            foldService.of((_state, lineStart, lineEnd) => {
              const candidates = syntaxRef.current?.folds.filter((item) => item.from >= lineStart && item.from <= lineEnd) ?? [];
              const fold = candidates.sort((left, right) => right.to - left.to)[0];
              return fold ? { from: fold.from, to: fold.to } : null;
            }),
          ] : []),
          editorTheme,
          EditorState.readOnly.of(readOnly),
          EditorView.editable.of(!readOnly),
          EditorView.updateListener.of((update) => {
            if (!update.docChanged) return;
            onChangeRef.current(update.state.doc.toString());
            parseSyntax(
              update.state.doc.toString(),
              update.startState.doc.length,
              pythonSyntaxEdits(update.changes, update.startState.doc, update.state.doc),
            );
          }),
        ],
      }),
    });
    viewRef.current = view;
    syntaxRef.current = null;
    setSyntaxSnapshot(null);
    if (isPython) parseSyntax(value, null, []);
    return () => {
      active = false;
      syntaxService?.terminate();
      viewRef.current = null;
      view.destroy();
    };
  }, [path, readOnly]);

  useEffect(() => {
    const view = viewRef.current;
    if (!view || view.state.doc.toString() === value) return;
    view.dispatch({ changes: { from: 0, to: view.state.doc.length, insert: value } });
  }, [value]);

  useEffect(() => {
    const view = viewRef.current;
    if (!view || !anchorLine || anchorLine < 1) return;
    const line = view.state.doc.line(Math.min(anchorLine, view.state.doc.lines));
    view.dispatch({
      selection: { anchor: line.from },
      effects: EditorView.scrollIntoView(line.from, { y: "center" }),
    });
  }, [anchorLine, path]);

  const navigate = (position: number) => {
    const view = viewRef.current;
    if (!view) return;
    view.dispatch({
      selection: { anchor: Math.min(position, view.state.doc.length) },
      effects: EditorView.scrollIntoView(position, { y: "center" }),
    });
    view.focus();
  };

  const isPython = path.toLowerCase().endsWith(".py");
  return <div className={`codemirror-editor-shell ${isPython ? "with-local-syntax" : ""}`}>
    <div className="codemirror-host" ref={hostRef} />
    {isPython ? <footer className={`codemirror-syntax-bar ${syntaxStatus}`} data-syntax-source="editor-local" data-syntax-status={syntaxStatus} data-syntax-parse-mode={syntaxSnapshot?.parseMode ?? "pending"}>
      <span>Tree-sitter · {syntaxStatus === "loading" ? "解析中" : syntaxStatus === "failed" ? "不可用" : `${syntaxSnapshot?.diagnostics.length ?? 0} errors`}</span>
      <select aria-label="本地结构导航" value="" disabled={syntaxStatus !== "ready" || !syntaxSnapshot?.symbols.length} onChange={(event) => {
        const symbol = syntaxSnapshot?.symbols[Number(event.target.value)];
        if (symbol) navigate(symbol.from);
      }}>
        <option value="">结构导航</option>
        {syntaxSnapshot?.symbols.map((symbol, index) => <option key={`${symbol.kind}:${symbol.from}:${symbol.name}`} value={index}>{symbol.kind === "class" ? "C" : "ƒ"} {symbol.name} · L{symbol.line}</option>)}
      </select>
    </footer> : null}
  </div>;
}
