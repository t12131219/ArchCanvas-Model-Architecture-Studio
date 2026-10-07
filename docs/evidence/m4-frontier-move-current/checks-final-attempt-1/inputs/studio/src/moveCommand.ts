import type { MoveScope, VisualOperation } from './core/types.ts';
import { resolveMoveScope } from './core/document.ts';

type Move = Extract<VisualOperation, { type: 'move' }>;
export type MoveCommand =
  | { status: 'none' }
  | { status: 'invalid'; reason: string }
  | { status: 'ready'; operation: Move };

const prefix = '(?:(仅当前视图|只在当前视图|在当前视图|当前视图|所有视图|全部视图|在所有视图)[，,\\s]*)?';
const target = '(?:将|让)?(?:所选对象|选中对象|选中节点|该节点)?[，,\\s]*';
const direction = '(?:向|往)?([上下左右])(?:移动|移)';
const command = new RegExp(`^${prefix}${target}${direction}\\s*(\\d+(?:\\.\\d+)?)\\s*(?:画布单位|单位)?[。.!！]?$`);
const attemptedMove = new RegExp(`^${prefix}${target}${direction}`);

/** A bounded local instruction; distances are canvas units, never screen pixels. */
export function parseMoveCommand(text: string, ids: readonly string[], defaultScope: MoveScope = 'all-frontiers'): MoveCommand {
  const value = text.trim(), match = command.exec(value);
  if (!match) return attemptedMove.test(value)
    ? { status: 'invalid', reason: '请输入明确的方向和正数距离，例如：仅当前视图，向右移动 24 画布单位。' }
    : { status: 'none' };
  const distance = Number(match[3]);
  if (!Number.isFinite(distance) || distance <= 0) return { status: 'invalid', reason: '移动距离必须是大于 0 的有限数值。' };
  if (!ids.length) return { status: 'invalid', reason: '先选择要移动的对象。' };
  const scope = match[1] ? match[1].includes('当前') ? 'current-frontier' : 'all-frontiers' : resolveMoveScope(defaultScope);
  const axis = match[2];
  return { status: 'ready', operation: { type: 'move', ids: [...new Set(ids)],
    dx: axis === '左' ? -distance : axis === '右' ? distance : 0,
    dy: axis === '上' ? -distance : axis === '下' ? distance : 0, scope } };
}
