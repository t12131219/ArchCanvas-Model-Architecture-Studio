import { getStudioJson } from "../../api/studio-client";

export interface SourceExcerpt {
  path: string;
  sha256: string;
  revision: string;
  start_line: number;
  end_line: number;
  highlight_start_line: number;
  highlight_end_line: number;
  lines: Array<{ number: number; text: string }>;
}

export function loadSourceExcerpt(
  path: string,
  startLine: number,
  endLine: number,
  signal?: AbortSignal,
): Promise<SourceExcerpt> {
  const query = new URLSearchParams({
    path,
    start: String(startLine),
    end: String(endLine),
    context: "4",
  });
  return getStudioJson<SourceExcerpt>(`/api/source-excerpt?${query}`, { signal });
}
