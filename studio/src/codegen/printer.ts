import type {
  AssignmentTarget,
  PrintedPyTorchDraft,
  PyTorchDraft,
  PythonExpression,
  PythonLiteral,
  PyTorchStatement,
  SourceBinding,
} from "./pytorch-ir";

const IDENTIFIER = /^[A-Za-z_][A-Za-z0-9_]*$/;

function assertIdentifier(value: string): string {
  if (!IDENTIFIER.test(value)) {
    throw new Error(`unsafe Python identifier: ${value}`);
  }
  return value;
}

function printLiteral(value: PythonLiteral): string {
  if (value === null) return "None";
  if (value === true) return "True";
  if (value === false) return "False";
  if (typeof value === "number") {
    if (!Number.isFinite(value)) throw new Error("Python literals must be finite numbers");
    if (Number.isInteger(value) && !Number.isSafeInteger(value)) {
      throw new Error("integer literal exceeds the cross-runtime safe range");
    }
    return Object.is(value, -0) ? "-0.0" : String(value);
  }
  if (typeof value === "string") {
    return JSON.stringify(value)
      .replaceAll("\u2028", "\\u2028")
      .replaceAll("\u2029", "\\u2029");
  }
  if (Array.isArray(value)) return `[${value.map(printLiteral).join(", ")}]`;
  const entries = Object.entries(value).sort(([left], [right]) => left.localeCompare(right));
  return `{${entries.map(([key, item]) => `${printLiteral(key)}: ${printLiteral(item)}`).join(", ")}}`;
}

function printExpression(expression: PythonExpression): string {
  switch (expression.kind) {
    case "name":
      return assertIdentifier(expression.identifier);
    case "attribute":
      return `${printExpression(expression.value)}.${assertIdentifier(expression.attribute)}`;
    case "literal":
      return printLiteral(expression.value);
    case "list":
      return `[${expression.items.map(printExpression).join(", ")}]`;
    case "tuple": {
      const values = expression.items.map(printExpression).join(", ");
      return `(${values}${expression.items.length === 1 ? "," : ""})`;
    }
    case "call": {
      const args = [
        ...expression.positional.map(printExpression),
        ...expression.keywords.map(({ name, value }) => `${assertIdentifier(name)}=${printExpression(value)}`),
      ];
      return `${printExpression(expression.callee)}(${args.join(", ")})`;
    }
  }
}

function printTarget(target: AssignmentTarget): string {
  if (target.kind === "discard") return "_";
  if (target.kind === "name") return assertIdentifier(target.identifier);
  return `(${target.items.map(printTarget).join(", ")})`;
}

interface Writer {
  lines: string[];
  sourceMap: Record<string, Array<{ startLine: number; endLine: number; nodeId: string; portIds: string[] }>>;
}

function addBinding(writer: Writer, binding: SourceBinding, startLine: number, endLine: number): void {
  const entry = { startLine, endLine, nodeId: binding.nodeId, portIds: [...binding.portIds] };
  writer.sourceMap[binding.nodeId] = [...(writer.sourceMap[binding.nodeId] ?? []), entry];
}

function writeStatement(writer: Writer, statement: PyTorchStatement, indent: string): void {
  const startLine = writer.lines.length + 1;
  if (statement.kind === "module-init") {
    writer.lines.push(`${indent}self.${assertIdentifier(statement.fieldId)} = ${printExpression(statement.value)}`);
  } else if (statement.kind === "assignment") {
    writer.lines.push(`${indent}${printTarget(statement.target)} = ${printExpression(statement.value)}`);
  } else {
    writer.lines.push(`${indent}for ${assertIdentifier(statement.target)} in ${printExpression(statement.iterable)}:`);
    for (const child of statement.body) writeStatement(writer, child, `${indent}    `);
    if (!statement.body.length) writer.lines.push(`${indent}    pass`);
  }
  addBinding(writer, statement.source, startLine, writer.lines.length);
}

export function printPyTorchDraft(draft: PyTorchDraft): PrintedPyTorchDraft {
  const writer: Writer = { lines: [], sourceMap: {} };
  const imports = [...draft.imports].sort((left, right) =>
    `${left.module}:${left.name ?? ""}:${left.alias ?? ""}`.localeCompare(
      `${right.module}:${right.name ?? ""}:${right.alias ?? ""}`,
    ),
  );
  for (const item of imports) {
    const alias = item.alias ? ` as ${assertIdentifier(item.alias)}` : "";
    writer.lines.push(
      item.name
        ? `from ${item.module.split(".").map(assertIdentifier).join(".")} import ${assertIdentifier(item.name)}${alias}`
        : `import ${item.module.split(".").map(assertIdentifier).join(".")}${alias}`,
    );
  }
  writer.lines.push("", `class ${assertIdentifier(draft.className)}(nn.Module):`, "    def __init__(self):", "        super().__init__()");
  if (!draft.fields.length) writer.lines.push("        pass");
  for (const statement of draft.fields) writeStatement(writer, statement, "        ");
  const parameters = draft.forwardParameters.map(assertIdentifier);
  writer.lines.push("", `    def forward(self${parameters.length ? `, ${parameters.join(", ")}` : ""}):`);
  if (!draft.forward.length) writer.lines.push("        pass");
  for (const statement of draft.forward) writeStatement(writer, statement, "        ");
  writer.lines.push(`        return ${printExpression(draft.returns)}`, "");
  return { source: writer.lines.join("\n"), sourceMap: writer.sourceMap };
}

