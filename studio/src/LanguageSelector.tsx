import { getLocale, locales, setLocale } from './i18n';

export function LanguageSelector() {
  return <label className="language-selector" title="界面语言 / Interface language">
    <span aria-hidden="true">文/A</span>
    <select aria-label="界面语言 / Interface language" value={getLocale()} onChange={event => setLocale(event.target.value)}>
      {locales.map(locale => <option key={locale.id} value={locale.id}>{locale.label}</option>)}
    </select>
  </label>;
}
