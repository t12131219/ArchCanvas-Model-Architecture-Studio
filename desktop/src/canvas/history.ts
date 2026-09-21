export type VisualHistory<T> = { entries: T[]; index: number }

export function appendHistory<T>(history: VisualHistory<T>, next: T): VisualHistory<T> {
  const index = history.index + 1
  return { entries: [...history.entries.slice(0, index), next], index }
}

