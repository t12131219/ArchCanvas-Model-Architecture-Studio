import { StudioApiError } from "../../api/studio-client";

export async function exportSceneRaster(
  svg: string,
  format: "png" | "pdf",
  nonce?: string,
): Promise<Blob> {
  const response = await fetch("/api/scene-export", {
    method: "POST",
    cache: "no-store",
    headers: {
      "Content-Type": "application/json",
      ...(nonce ? { "X-ArchCanvas-Nonce": nonce } : {}),
    },
    body: JSON.stringify({ svg, format }),
  });
  if (!response.ok) {
    throw new StudioApiError(
      "/api/scene-export",
      response.status,
      (await response.text()) || response.statusText,
    );
  }
  return response.blob();
}
