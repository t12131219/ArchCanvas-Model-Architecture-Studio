/** User document names are data and never translated with the interface. */
export function modelName(value: string): string {
  const name = value.trim();
  if (!name || name.length > 240 || /[\u0000-\u001f\u007f]/.test(name)) {
    throw new Error('名称须为 1–240 个字符，不能含控制字符。');
  }
  return name;
}
