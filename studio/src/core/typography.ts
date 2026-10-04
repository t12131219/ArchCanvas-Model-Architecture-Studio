/** Conservative deterministic measurement, including wide CJK characters. */
export function textWidth(text: string, size = 13): number {
  return [...text].reduce((width, char) => width + (/[^\u0000-\u00ff]/u.test(char) ? size : /[il.,' ]/.test(char) ? size * .32 : size * .56), 0);
}
export function wrapText(text: string, width: number, size = 13): string[] {
  const lines: string[] = [];
  for (const paragraph of text.split('\n')) {
    let current = '';
    for (const char of [...paragraph]) {
      if (current && textWidth(current + char, size) > width) { lines.push(current.trimEnd()); current = ''; }
      current += char;
    }
    lines.push(current.trimEnd());
  }
  return lines;
}
