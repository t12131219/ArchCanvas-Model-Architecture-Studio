import { defaultKeymap, history, historyKeymap } from "@codemirror/commands";
import { json } from "@codemirror/lang-json";
import { python } from "@codemirror/lang-python";
import { defaultHighlightStyle, syntaxHighlighting } from "@codemirror/language";
import { EditorState } from "@codemirror/state";
import {
  EditorView,
  highlightActiveLine,
  highlightActiveLineGutter,
  highlightSpecialChars,
  keymap,
  lineNumbers,
} from "@codemirror/view";
import { useEffect, useRef } from "react";

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
  const onChangeRef = useRef(onChange);
  onChangeRef.current = onChange;

  useEffect(() => {
    const host = hostRef.current;
    if (!host) return;
    const language = path.toLowerCase().endsWith(".json") ? json() : python();
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
          keymap.of([...defaultKeymap, ...historyKeymap]),
          language,
          editorTheme,
          EditorState.readOnly.of(readOnly),
          EditorView.editable.of(!readOnly),
          EditorView.updateListener.of((update) => {
            if (update.docChanged) onChangeRef.current(update.state.doc.toString());
          }),
        ],
      }),
    });
    viewRef.current = view;
    return () => {
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

  return <div className="codemirror-host" ref={hostRef} />;
}
