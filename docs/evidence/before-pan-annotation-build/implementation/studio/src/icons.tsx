import type { CSSProperties } from 'react';
export function Icon({ name, size = 18, style }: { name: string; size?: number; style?: CSSProperties }) {
  const paths: Record<string, React.ReactNode> = {
    arrow: <><path d="m5 3 13 8-6 2-2 6Z" /></>,
    undo: <><path d="M3 10h11a6 6 0 0 1 0 12M3 10l5-5M3 10l5 5" /></>,
    redo: <><path d="M21 10H10a6 6 0 0 0 0 12M21 10l-5-5M21 10l-5 5" /></>,
    save: <><path d="M5 3h12l4 4v14H3V3h2Z" /><path d="M7 3v6h10V3M7 21v-8h10v8" /></>,
    export: <><path d="M12 16V3m-5 5 5-5 5 5M4 14v7h16v-7" /></>,
    fit: <><path d="M8 3H3v5m13-5h5v5M3 16v5h5m13-5v5h-5" /><rect x="7" y="7" width="10" height="10" rx="1" /></>,
    plus: <path d="M12 5v14M5 12h14" />,
    minus: <path d="M5 12h14" />,
    chevron: <path d="m9 5 7 7-7 7" />,
    code: <><path d="m7 7-5 5 5 5m10-10 5 5-5 5m-3-14-4 18" /></>,
    layers: <><path d="m12 3 10 6-10 6L2 9Zm-9 10 9 5 9-5m-18 5 9 5 9-5" /></>,
    pin: <><path d="m8 3 8 0-1 6 4 4H5l4-4Zm4 10v9" /></>,
    align: <><path d="M5 3v18" /><rect x="8" y="5" width="11" height="5" rx="1" /><rect x="8" y="14" width="8" height="5" rx="1" /></>,
    close: <path d="m6 6 12 12M18 6 6 18" />,
    check: <path d="m5 12 4 4L19 6" />,
    info: <><circle cx="12" cy="12" r="9" /><path d="M12 11v6M12 7v1" /></>,
    file: <><path d="M5 3h9l5 5v13H5Z" /><path d="M14 3v6h5M8 13h8M8 17h6" /></>,
    message: <><path d="M4 4h16v12H9l-5 4Z" /><path d="M8 8h8M8 12h5" /></>,
    grid: <><rect x="3" y="3" width="7" height="7" rx="1" /><rect x="14" y="3" width="7" height="7" rx="1" /><rect x="3" y="14" width="7" height="7" rx="1" /><rect x="14" y="14" width="7" height="7" rx="1" /></>,
  };
  return <svg width={size} height={size} viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="1.6" strokeLinecap="round" strokeLinejoin="round" style={style} aria-hidden="true">{paths[name] ?? paths.file}</svg>;
}
