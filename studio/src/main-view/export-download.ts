function sanitizeFilename(value: string): string {
  const cleaned = value.trim().replace(/[^a-zA-Z0-9._-]+/g, "-").replace(/^-+|-+$/g, "");
  return cleaned || "archcanvas-main-view";
}

function triggerDownload(blob: Blob, filename: string): void {
  const url = URL.createObjectURL(blob);
  const anchor = document.createElement("a");
  anchor.href = url;
  anchor.download = filename;
  anchor.style.display = "none";
  document.body.append(anchor);
  anchor.click();
  anchor.remove();
  window.setTimeout(() => URL.revokeObjectURL(url), 0);
}

export function downloadKernelSvg(svg: string, basename: string): void {
  triggerDownload(new Blob([svg], { type: "image/svg+xml;charset=utf-8" }), `${sanitizeFilename(basename)}.svg`);
}

async function loadSvgImage(svg: string): Promise<HTMLImageElement> {
  const url = URL.createObjectURL(new Blob([svg], { type: "image/svg+xml;charset=utf-8" }));
  try {
    const image = new Image();
    image.decoding = "async";
    await new Promise<void>((resolve, reject) => {
      image.onload = () => resolve();
      image.onerror = () => reject(new Error("The kernel SVG could not be rasterized."));
      image.src = url;
    });
    return image;
  } finally {
    URL.revokeObjectURL(url);
  }
}

async function rasterizeSvg(
  svg: string,
  width: number,
  height: number,
  scale: number,
): Promise<HTMLCanvasElement> {
  const maxDimension = 8192;
  const safeScale = Math.min(Math.max(0.25, scale), maxDimension / Math.max(width, height));
  const canvas = document.createElement("canvas");
  canvas.width = Math.max(1, Math.round(width * safeScale));
  canvas.height = Math.max(1, Math.round(height * safeScale));
  const context = canvas.getContext("2d");
  if (!context) throw new Error("Canvas rendering is unavailable in this browser.");
  context.fillStyle = "#fbfcfa";
  context.fillRect(0, 0, canvas.width, canvas.height);
  context.drawImage(await loadSvgImage(svg), 0, 0, canvas.width, canvas.height);
  return canvas;
}

function canvasBlob(canvas: HTMLCanvasElement, type: string, quality?: number): Promise<Blob> {
  return new Promise((resolve, reject) => canvas.toBlob((blob) => {
    if (blob) resolve(blob);
    else reject(new Error(`Browser failed to encode ${type}.`));
  }, type, quality));
}

export async function svgToPngBlob(svg: string, width: number, height: number, scale = 2): Promise<Blob> {
  return canvasBlob(await rasterizeSvg(svg, width, height, scale), "image/png");
}

function ascii(value: string): Uint8Array {
  return new TextEncoder().encode(value);
}

function concatBytes(parts: Uint8Array[]): Uint8Array {
  const total = parts.reduce((sum, part) => sum + part.length, 0);
  const result = new Uint8Array(total);
  let offset = 0;
  for (const part of parts) {
    result.set(part, offset);
    offset += part.length;
  }
  return result;
}

function jpegPdf(jpeg: Uint8Array, pixelWidth: number, pixelHeight: number, sceneWidth: number, sceneHeight: number): Uint8Array {
  const maxPageDimension = 1440;
  const pageScale = Math.min(1, maxPageDimension / Math.max(sceneWidth, sceneHeight));
  const pageWidth = Math.max(1, sceneWidth * pageScale);
  const pageHeight = Math.max(1, sceneHeight * pageScale);
  const content = ascii(`q\n${pageWidth.toFixed(3)} 0 0 ${pageHeight.toFixed(3)} 0 0 cm\n/Im0 Do\nQ\n`);
  const objects: Uint8Array[] = [
    ascii("<< /Type /Catalog /Pages 2 0 R >>"),
    ascii("<< /Type /Pages /Kids [3 0 R] /Count 1 >>"),
    ascii(`<< /Type /Page /Parent 2 0 R /MediaBox [0 0 ${pageWidth.toFixed(3)} ${pageHeight.toFixed(3)}] /Resources << /XObject << /Im0 4 0 R >> >> /Contents 5 0 R >>`),
    concatBytes([
      ascii(`<< /Type /XObject /Subtype /Image /Width ${pixelWidth} /Height ${pixelHeight} /ColorSpace /DeviceRGB /BitsPerComponent 8 /Filter /DCTDecode /Length ${jpeg.length} >>\nstream\n`),
      jpeg,
      ascii("\nendstream"),
    ]),
    concatBytes([ascii(`<< /Length ${content.length} >>\nstream\n`), content, ascii("endstream")]),
    ascii("<< /Producer (ArchCanvas Visual Kernel) /Creator (ArchCanvas Studio) >>"),
  ];
  const chunks: Uint8Array[] = [new Uint8Array([0x25, 0x50, 0x44, 0x46, 0x2d, 0x31, 0x2e, 0x34, 0x0a, 0x25, 0xe2, 0xe3, 0xcf, 0xd3, 0x0a])];
  const offsets = [0];
  let byteOffset = chunks[0].length;
  objects.forEach((object, index) => {
    offsets.push(byteOffset);
    const chunk = concatBytes([ascii(`${index + 1} 0 obj\n`), object, ascii("\nendobj\n")]);
    chunks.push(chunk);
    byteOffset += chunk.length;
  });
  const xrefOffset = byteOffset;
  const xref = ["xref", `0 ${objects.length + 1}`, "0000000000 65535 f ", ...offsets.slice(1).map((offset) => `${String(offset).padStart(10, "0")} 00000 n `)].join("\n");
  chunks.push(ascii(`${xref}\ntrailer\n<< /Size ${objects.length + 1} /Root 1 0 R /Info 6 0 R >>\nstartxref\n${xrefOffset}\n%%EOF\n`));
  return concatBytes(chunks);
}

export async function svgToPdfBlob(svg: string, width: number, height: number): Promise<Blob> {
  const canvas = await rasterizeSvg(svg, width, height, 1.5);
  const jpeg = new Uint8Array(await (await canvasBlob(canvas, "image/jpeg", 0.94)).arrayBuffer());
  const pdf = jpegPdf(jpeg, canvas.width, canvas.height, width, height);
  const buffer = new ArrayBuffer(pdf.byteLength);
  new Uint8Array(buffer).set(pdf);
  return new Blob([buffer], { type: "application/pdf" });
}

export async function downloadKernelPng(svg: string, width: number, height: number, basename: string): Promise<void> {
  triggerDownload(await svgToPngBlob(svg, width, height), `${sanitizeFilename(basename)}.png`);
}

export async function downloadKernelPdf(svg: string, width: number, height: number, basename: string): Promise<void> {
  triggerDownload(await svgToPdfBlob(svg, width, height), `${sanitizeFilename(basename)}.pdf`);
}
