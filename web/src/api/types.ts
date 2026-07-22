// Transport shapes mirrored from the FastAPI /api/v1 contracts. Kept minimal for the scaffold;
// later work generates or validates these against the OpenAPI document.

export interface Capability {
  available: boolean;
  reason?: string;
}

export interface LibrarySummary {
  id: string;
  display_name: string;
  last_opened_at: string | null;
  health: string;
  clip_count: number;
  is_active: boolean;
}

export interface Bootstrap {
  app_version: string;
  active_library: LibrarySummary | null;
  libraries: LibrarySummary[];
  capabilities: Record<string, Capability>;
  worker: { state: string };
}
