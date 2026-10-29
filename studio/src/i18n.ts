import english from './locales/en.json' with { type: 'json' };

export type Locale = 'zh-CN' | 'en';
export const localeKey = 'archcanvas.ui.locale.v1';
export const locales: { id: Locale; label: string }[] = [{ id: 'zh-CN', label: '中文' }, { id: 'en', label: 'English' }];
const dictionaries: Record<Locale, Record<string, string>> = { 'zh-CN': {}, en: english };
function savedLocale(): Locale {
  try { return localStorage.getItem(localeKey) === 'en' ? 'en' : 'zh-CN'; } catch { return 'zh-CN'; }
}
let locale = savedLocale();
const listeners = new Set<() => void>();
export const getLocale = () => locale;
export function subscribeLocale(listener: () => void) { listeners.add(listener); return () => { listeners.delete(listener); }; }
export function setLocale(value: string) {
  if (!locales.some(item => item.id === value)) return;
  locale = value as Locale;
  try { localStorage.setItem(localeKey, locale); } catch { /* Private browsing may disallow persistence. */ }
  if (typeof document !== 'undefined') document.documentElement.lang = locale;
  for (const listener of listeners) listener();
}
/** Only explicit UI message keys pass here. Interpolated values remain opaque data. */
export function t(key: string, values: Record<string, unknown> = {}): string {
  const text = dictionaries[locale][key] ?? key;
  return text.replace(/\{(\d+)\}/g, (token, index: string) => Object.hasOwn(values, index) ? String(values[index]) : token);
}
/** Notifications may arrive from a worker or be stored before a locale switch. */
export function uiMessage(value: string): string {
  if (locale !== 'en') return value;
  const prefix = value.startsWith('Error: ') ? 'Error: ' : '';
  const text = value.slice(prefix.length);
  if (Object.hasOwn(english, text)) return prefix + t(text);
  for (const [key, translated] of Object.entries(english)) {
    if (!/\{\d+\}/.test(key)) continue;
    const indices: string[] = [];
    const pattern = key.split(/(\{\d+\})/).map(part => {
      if (/^\{\d+\}$/.test(part)) { indices.push(part.slice(1, -1)); return '([\\s\\S]*?)'; }
      return part.replace(/[.*+?^${}()|[\]\\]/g, '\\$&');
    }).join('');
    const match = new RegExp('^' + pattern + '$').exec(text);
    if (match) return prefix + translated.replace(/\{(\d+)\}/g, (token, index: string) => match[indices.indexOf(index) + 1] ?? token);
  }
  return value;
}
