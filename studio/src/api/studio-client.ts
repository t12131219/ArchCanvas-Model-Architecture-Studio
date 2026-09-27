export class StudioApiError extends Error {
  constructor(
    readonly endpoint: string,
    readonly status: number,
    message: string,
  ) {
    super(message);
    this.name = "StudioApiError";
  }
}

async function decode<T>(endpoint: string, response: Response): Promise<T> {
  if (!response.ok) {
    const message = await response.text();
    throw new StudioApiError(endpoint, response.status, message || response.statusText);
  }
  return response.json() as Promise<T>;
}

export function getStudioJson<T>(
  endpoint: string,
  options: { signal?: AbortSignal } = {},
): Promise<T> {
  return fetch(endpoint, {
    cache: "no-store",
    signal: options.signal,
  }).then((response) => decode<T>(endpoint, response));
}

export function postStudioJson<T>(
  endpoint: string,
  payload: unknown = {},
  options: { nonce?: string; signal?: AbortSignal } = {},
): Promise<T> {
  return fetch(endpoint, {
    method: "POST",
    cache: "no-store",
    signal: options.signal,
    headers: {
      "Content-Type": "application/json",
      ...(options.nonce ? { "X-ArchCanvas-Nonce": options.nonce } : {}),
    },
    body: JSON.stringify(payload),
  }).then((response) => decode<T>(endpoint, response));
}
