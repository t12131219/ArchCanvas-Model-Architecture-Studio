import { Braces, CircleDot, X } from "lucide-react";

import type { GraphDelta, SourceTransaction } from "../app/studio-types";

function displayValue(value: unknown): string {
  if (typeof value === "string") return value;
  try { return JSON.stringify(value); } catch { return String(value); }
}

function deltaSummary(delta: GraphDelta | undefined, tx: (english: string, chinese: string) => string): string {
  if (!delta) return tx("Not available", "不可用");
  const nodes = delta.added_nodes.length + delta.removed_nodes.length + delta.changed_nodes.length;
  const edges = delta.added_edges.length + delta.removed_edges.length + delta.changed_edges.length;
  return `${delta.changed_parameters.length} ${tx("parameters", "个参数")} · ${nodes} ${tx("nodes", "个节点")} · ${edges} ${tx("edges", "条边")} · ${delta.changed_shapes.length} ${tx("shapes", "个形状")}`;
}

export function TransactionReview({ transaction, writebackBlocked, tx, onCommit, onDiscard }: {
  transaction: SourceTransaction;
  writebackBlocked: boolean;
  tx: (english: string, chinese: string) => string;
  onCommit: () => Promise<void>;
  onDiscard: () => Promise<void>;
}) {
  return <div className="transaction-review">
    <section><h3>{tx("Source diff", "源码差异")}</h3><pre>{transaction.source_diff || tx("No textual change", "没有文本变化")}</pre></section>
    <section><h3>Graph Delta</h3><dl><dt>{tx("Expected", "预期")}</dt><dd>{deltaSummary(transaction.expected_delta, tx)}</dd><dt>{tx("Observed", "观测")}</dt><dd>{deltaSummary(transaction.observed_delta, tx)}</dd></dl>{transaction.expected_delta.changed_parameters.map((item) => <code key={`${item.node_id}-${item.parameter_name}`}>{item.node_id}.{item.parameter_name}: {displayValue(item.before)} → {displayValue(item.after)}</code>)}</section>
    <section><h3>{tx("Validation receipt", "验证凭据")}</h3><div className="gate-list">{transaction.gates.map((gate) => <span key={gate.gate} className={gate.status}>{gate.status} · {gate.gate}</span>)}</div><div className="review-actions">{transaction.state === "review-ready" ? <button className="commit-button" disabled={writebackBlocked} title={writebackBlocked ? tx("Resolve draft blockers before committing", "提交前请解决草稿阻断项") : tx("Commit verified source transaction", "提交已验证的源码事务")} onClick={() => void onCommit()}><CircleDot size={14} /> {tx("Commit to source", "提交到源码")}</button> : <span className="agent-handoff-status"><Braces size={14} /> {tx("No commit action until every validation gate passes", "全部验证门通过后才可提交")}</span>} {!['committed', 'discarded'].includes(transaction.state) && <button onClick={() => void onDiscard()}><X size={14} /> {tx("Discard", "放弃")}</button>}</div></section>
  </div>;
}
