import type { ModuleSymbol as SymbolKind } from './moduleSymbols';
export function ModuleSymbol({ symbol }: { symbol: SymbolKind }) {
  const paths = {
    module: <><rect x="3" y="4" width="18" height="16" rx="3"/><path d="M3 9h18"/></>,
    variable: <><path d="M7 4H4v16h3m10-16h3v16h-3M9 9l6 6m0-6-6 6"/></>,
    matrix: <><path d="M6 3H3v18h3M18 3h3v18h-3M9 7h1m4 0h1m-6 5h1m4 0h1m-6 5h1m4 0h1"/></>,
    add: <><circle cx="12" cy="12" r="9"/><path d="M7 12h10m-5-5v10"/></>,
    multiply: <><path d="m6 6 12 12M18 6 6 18"/></>,
    hadamard: <><circle cx="12" cy="12" r="9"/><circle cx="12" cy="12" r="2" fill="currentColor"/></>,
    matmul: <><path d="M6 4H3v16h3m12-16h3v16h-3m-9-12 6 8m0-8-6 8"/></>,
    activation: <><path d="M3 20V4m0 16h18M5 17c8 0 3-10 14-10"/></>,
    linear: <><circle cx="5" cy="5" r="2"/><circle cx="5" cy="19" r="2"/><circle cx="19" cy="12" r="2"/><path d="m7 6 10 5M7 18l10-5"/></>,
    norm: <><path d="M4 7h16M4 17h16M8 12h8"/></>,
    attention: <><circle cx="5" cy="6" r="2"/><circle cx="19" cy="6" r="2"/><circle cx="12" cy="19" r="2"/><path d="m6 8 5 9m7-9-5 9M7 6h10"/></>,
    reshape: <><rect x="3" y="3" width="11" height="7" rx="1"/><path d="m16 8 5 4-5 4m5-4h-9"/><rect x="3" y="14" width="6" height="7" rx="1"/></>,
    unknown: <><rect x="3" y="3" width="18" height="18" rx="4"/><path d="M9 8a3 3 0 0 1 6 0c0 2-3 2-3 5m0 3v1"/></>,
  };
  return <svg aria-hidden="true" width="16" height="16" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="1.6" strokeLinecap="round" strokeLinejoin="round">{paths[symbol]}</svg>;
}
