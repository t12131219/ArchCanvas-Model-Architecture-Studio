import { useEffect, useRef, type RefObject } from 'react';

/** One transient menu at a time, with consistent pointer and keyboard dismissal. */
export function useWorkspaceMenus() {
  useEffect(() => {
    const menus = () => [...document.querySelectorAll<HTMLDetailsElement>('details.workspace-menu[open], details.alignment-menu[open], details.selection-menu[open], details.canvas-options[open]')];
    const pointer = (event: Event) => {
      for (const menu of menus()) if (!menu.contains(event.target as Node)) menu.open = false;
    };
    const toggle = (event: Event) => { const target = event.target; if (target instanceof HTMLDetailsElement && target.open && target.matches('details.workspace-menu,details.alignment-menu,details.selection-menu,details.canvas-options')) for (const menu of menus()) if (menu !== target) menu.open = false; };
    const click = (event: MouseEvent) => {
      const button = (event.target as Element).closest('button');
      if (button && !button.disabled) button.closest<HTMLDetailsElement>('details.workspace-menu,details.selection-menu,details.canvas-options')?.removeAttribute('open');
    };
    const key = (event: KeyboardEvent) => {
      if (event.key === 'Escape') {
        const open = menus();
        if (open.length) { event.preventDefault(); open.at(-1)?.querySelector<HTMLElement>('summary')?.focus(); open.forEach(menu => { menu.open = false; }); }
      }
      if (event.key === 'ArrowDown' || event.key === 'ArrowUp') {
        const menu = (event.target as Element).closest<HTMLDetailsElement>('details.workspace-menu,details.alignment-menu,details.selection-menu,details.canvas-options');
        if (!menu) return;
        const buttons = [...menu.querySelectorAll<HTMLButtonElement>('button:not(:disabled)')];
        if (!buttons.length) return;
        menu.open = true; event.preventDefault();
        const index = buttons.indexOf(event.target as HTMLButtonElement);
        buttons[index < 0 ? (event.key === 'ArrowDown' ? 0 : buttons.length - 1) : (index + (event.key === 'ArrowDown' ? 1 : buttons.length - 1)) % buttons.length].focus();
      }
    };
    // Clicking into an iframe is an outside interaction, too.
    const blur = () => { if (document.activeElement?.tagName === 'IFRAME') menus().forEach(menu => { menu.open = false; }); };
    document.addEventListener('pointerdown', pointer, true);
    document.addEventListener('focusin', pointer);
    document.addEventListener('toggle', toggle, true);
    document.addEventListener('click', click);
    document.addEventListener('keydown', key);
    window.addEventListener('blur', blur);
    return () => { document.removeEventListener('pointerdown', pointer, true); document.removeEventListener('focusin', pointer); document.removeEventListener('toggle', toggle, true); document.removeEventListener('click', click); document.removeEventListener('keydown', key); window.removeEventListener('blur', blur); };
  }, []);
}

/** Dialog focus stays inside the active form and returns to its opener. */
export function useModalFocus<T extends HTMLElement>(onClose: () => void): RefObject<T | null> {
  const ref = useRef<T>(null);
  const close = useRef(onClose); close.current = onClose;
  useEffect(() => {
    const previous = document.activeElement as HTMLElement | null;
    const panel = ref.current;
    if (!panel) return;
    const controls = () => [...panel.querySelectorAll<HTMLElement>('button:not(:disabled),input:not([hidden]),textarea,select,[tabindex="0"]')].filter(node => node.getClientRects().length);
    controls()[0]?.focus();
    const key = (event: KeyboardEvent) => {
      if (event.key === 'Escape') { event.preventDefault(); event.stopPropagation(); close.current(); }
      if (event.key === 'Tab') {
        const items = controls(), first = items[0], last = items.at(-1);
        if (event.shiftKey && document.activeElement === first) { event.preventDefault(); last?.focus(); }
        if (!event.shiftKey && document.activeElement === last) { event.preventDefault(); first?.focus(); }
      }
    };
    panel.addEventListener('keydown', key);
    return () => { panel.removeEventListener('keydown', key); previous?.focus(); };
  }, []);
  return ref;
}
