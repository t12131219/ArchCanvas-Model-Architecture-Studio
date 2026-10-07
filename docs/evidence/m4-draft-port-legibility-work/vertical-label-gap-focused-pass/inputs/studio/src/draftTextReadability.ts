/** Keep the small, always-visible canvas labels readable in overview zooms.
 *
 * The canvas still scales geometrically with the camera.  This bounded factor
 * only compensates the text size, so a 58% overview does not turn labels into
 * sub-six-pixel marks and a close-up never grows without limit.
 */
export function draftCanvasTextScale(zoom: number): number {
  if (!Number.isFinite(zoom) || zoom <= 0) return 1.8;
  return Math.min(1.8, Math.max(1, 0.9 / zoom));
}

/** Shortened canvas text retains its complete accessible/title content. */
export function draftFittedText(text: string, size: number, width: number, monospace = false): string {
  const advance = (value: string) => [...value].reduce((sum, char) => sum + size * (/[^\u0000-\u00ff]/u.test(char) ? 1 : monospace ? .65 : /[WM@]/.test(char) ? 1 : .75), 0);
  if (advance(text) <= width) return text;
  let label = '';
  for (const char of text) {
    if (advance(label + char + '…') > width) break;
    label += char;
  }
  return label + '…';
}
