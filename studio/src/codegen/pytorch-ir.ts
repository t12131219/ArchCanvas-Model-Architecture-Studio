export type PythonLiteral = null | boolean | number | string | PythonLiteral[] | {
  [key: string]: PythonLiteral;
};

export type PythonExpression =
  | { kind: "name"; identifier: string }
  | { kind: "attribute"; value: PythonExpression; attribute: string }
  | { kind: "literal"; value: PythonLiteral }
  | { kind: "list"; items: PythonExpression[] }
  | { kind: "tuple"; items: PythonExpression[] }
  | {
      kind: "call";
      callee: PythonExpression;
      positional: PythonExpression[];
      keywords: Array<{ name: string; value: PythonExpression }>;
    };

export type AssignmentTarget =
  | { kind: "name"; identifier: string }
  | { kind: "tuple"; items: AssignmentTarget[] }
  | { kind: "discard" };

export interface SourceBinding {
  nodeId: string;
  portIds: string[];
}

export interface ModuleInitStatement {
  kind: "module-init";
  fieldId: string;
  value: PythonExpression;
  source: SourceBinding;
}

export interface AssignmentStatement {
  kind: "assignment";
  target: AssignmentTarget;
  value: PythonExpression;
  source: SourceBinding;
}

export interface ForStatement {
  kind: "for";
  target: string;
  iterable: PythonExpression;
  body: PyTorchStatement[];
  source: SourceBinding;
}

export type PyTorchStatement = ModuleInitStatement | AssignmentStatement | ForStatement;

export interface ImportSpec {
  module: string;
  name?: string;
  alias?: string;
}

export interface PyTorchDraft {
  imports: ImportSpec[];
  className: string;
  forwardParameters: string[];
  fields: ModuleInitStatement[];
  forward: PyTorchStatement[];
  returns: PythonExpression;
}

export interface PrintedSourceSpan {
  startLine: number;
  endLine: number;
  nodeId: string;
  portIds: string[];
}

export interface PrintedPyTorchDraft {
  source: string;
  sourceMap: Record<string, PrintedSourceSpan[]>;
}

export function name(identifier: string): PythonExpression {
  return { kind: "name", identifier };
}

export function attribute(value: PythonExpression, property: string): PythonExpression {
  return { kind: "attribute", value, attribute: property };
}

export function literal(value: PythonLiteral): PythonExpression {
  return { kind: "literal", value };
}

export function call(
  callee: PythonExpression,
  positional: PythonExpression[] = [],
  keywords: Array<{ name: string; value: PythonExpression }> = [],
): PythonExpression {
  return { kind: "call", callee, positional, keywords };
}

