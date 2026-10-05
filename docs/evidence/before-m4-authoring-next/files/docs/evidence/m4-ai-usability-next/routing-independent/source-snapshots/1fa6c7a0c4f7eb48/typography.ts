/** Conservative deterministic measurement, including wide CJK characters. */
export function textWidth(text: string, size = 13): number {
  return [...text].reduce((width, char) => width + (/[^\u0000-\u00ff]/u.test(char) ? size : /[il.,' ]/.test(char) ? size * .32 : size * .56), 0);
}

const cjk = /[\p{Script=Han}\p{Script=Hiragana}\p{Script=Katakana}\p{Script=Hangul}]/u;
const whitespace = /\s/u;
// Keep source-path/identifier punctuation with its token, but allow a boundary
// beside standalone symbols such as emoji rather than splitting a fitting word.
const word = /[\p{L}\p{N}\p{M}\x21-\x7e]/u;

/** CJK/symbols can break between code points; whitespace delimits words. */
function* tokens(paragraph: string): Generator<{ text: string; space: boolean }> {
  let parts: string[] = [], isSpace = false;
  for (const char of paragraph) {
    const nextSpace = whitespace.test(char);
    if (cjk.test(char) || !nextSpace && !word.test(char)) {
      if (parts.length) { yield { text: parts.join(''), space: isSpace }; parts = []; }
      yield { text: char, space: false };
    } else {
      if (parts.length && nextSpace !== isSpace) { yield { text: parts.join(''), space: isSpace }; parts = []; }
      isSpace = nextSpace; parts.push(char);
    }
  }
  if (parts.length) yield { text: parts.join(''), space: isSpace };
}

/**
 * Keep fitting words/identifiers whole, falling back only for an oversized token.
 * Width accounting is linear in Unicode code points, including that fallback.
 * Explicit LF/CRLF/CR breaks and empty lines survive. Whitespace inside a line
 * is retained; whitespace at a line boundary is discarded. One code point wider
 * than the budget occupies a line by itself so even tiny budgets make progress.
 */
export function wrapText(text: string, width: number, size = 13): string[] {
  if (!Number.isFinite(width) || !Number.isFinite(size) || size <= 0) {
    throw new RangeError('Text wrapping requires a finite width and a positive finite font size');
  }
  // A valid narrow annotation can have zero/negative width after its text inset.
  // Treat that as no available advance, allowing the single-point fallback below.
  // Decimal advances such as .56 can accumulate a few floating-point ULPs.
  const tolerance = width > 0 ? Number.EPSILON * Math.max(width, size) * 16 : 0;
  const fits = (value: number) => value <= width || value - width <= tolerance;
  const lines: string[] = [];
  for (const paragraph of text.split(/\r\n|[\n\r]/u)) {
    let parts: string[] = [], used = 0, space = '', spaceWidth = 0;
    const flush = () => { lines.push(parts.join('')); parts = []; used = 0; };
    const start = lines.length;
    for (const token of tokens(paragraph)) {
      if (token.space) { space = token.text; spaceWidth = textWidth(space, size); continue; }
      const tokenWidth = textWidth(token.text, size);
      if (fits(tokenWidth)) {
        if (parts.length && !fits(used + spaceWidth + tokenWidth)) flush();
        if (parts.length && space) { parts.push(space); used += spaceWidth; }
        parts.push(token.text); used += tokenWidth;
      } else {
        // Start a too-wide token on a fresh line, then consume every code point.
        if (parts.length) flush();
        for (const char of token.text) {
          const charWidth = textWidth(char, size);
          if (parts.length && !fits(used + charWidth)) flush();
          parts.push(char); used += charWidth;
          if (!fits(charWidth)) flush();
        }
      }
      space = ''; spaceWidth = 0;
    }
    if (parts.length) flush();
    else if (lines.length === start) lines.push('');
  }
  return lines;
}
