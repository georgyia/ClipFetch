// Tiny typed fetch wrapper. All API access goes through here so error handling and the
// sanitized error envelope are consistent across the app.

export interface ApiErrorBody {
  error: {
    code: string;
    message: string;
    request_id: string | null;
    details?: { recovery_actions?: string[] };
  };
}

export class ApiError extends Error {
  readonly status: number;
  readonly code: string;

  constructor(status: number, code: string, message: string) {
    super(message);
    this.name = "ApiError";
    this.status = status;
    this.code = code;
  }
}

export async function apiGet<T>(path: string): Promise<T> {
  const response = await fetch(path, { headers: { Accept: "application/json" } });
  if (!response.ok) {
    let code = "http_error";
    let message = response.statusText || "Request failed";
    try {
      const body = (await response.json()) as ApiErrorBody;
      if (body?.error) {
        code = body.error.code;
        message = body.error.message;
      }
    } catch {
      // Non-JSON error body; keep the status-based defaults.
    }
    throw new ApiError(response.status, code, message);
  }
  return (await response.json()) as T;
}
