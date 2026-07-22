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

export interface ClipSummary {
  id: string;
  platform: string;
  author: string | null;
  caption: string | null;
  likes: number | null;
  views: number | null;
  comments_count: number | null;
  duration_seconds: number | null;
  published_at: string | null;
  downloaded_at: string;
  available: boolean;
  metadata_state: string;
  hashtags: string[];
  topics: string[];
  source_url: string | null;
}

export interface ClipDetail extends ClipSummary {
  schema_version: number;
  shares: number | null;
  file_size_bytes: number;
  has_transcript: boolean;
  transcript_status: string | null;
  transcript_language: string | null;
  has_comments: boolean;
  comment_status: string | null;
}

export interface ClipPage {
  schema_version: number;
  items: ClipSummary[];
  next_cursor: string | null;
  total_matched: number;
}

export interface Rail {
  id: string;
  title: string;
  kind: string;
  destination: string;
  items: ClipSummary[];
  next_cursor: string | null;
}

export interface HomeResponse {
  rails: Rail[];
}

export interface TopicSummary {
  slug: string;
  description: string | null;
  clip_count: number;
}

export interface CollectionSummary {
  id: string;
  filters: Record<string, unknown>;
  clip_count: number;
}

export interface SearchResult extends ClipPage {
  query: string;
  requested_mode: string;
  mode_used: string;
  semantic_available: boolean;
}

/** Media endpoints are addressed by clip id only; no filesystem paths ever reach the client. */
export function posterUrl(clipId: string): string {
  return `/api/v1/clips/${encodeURIComponent(clipId)}/poster`;
}

export function mediaUrl(clipId: string): string {
  return `/api/v1/clips/${encodeURIComponent(clipId)}/media`;
}
