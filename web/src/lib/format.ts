// Small presentation helpers shared across cards, rails, and the detail page.

/** Turn a slug like "street-food" into a display title "Street Food". */
export function titleize(slug: string): string {
  return slug
    .split(/[-_\s]+/)
    .filter(Boolean)
    .map((part) => part[0].toUpperCase() + part.slice(1))
    .join(" ");
}

/** Compact count: 1_234 -> "1.2K", 2_500_000 -> "2.5M". Null/negative render as an empty string. */
export function compactCount(value: number | null | undefined): string {
  if (value == null || value < 0) {
    return "";
  }
  if (value < 1000) {
    return String(value);
  }
  const units = [
    { limit: 1_000_000_000, suffix: "B" },
    { limit: 1_000_000, suffix: "M" },
    { limit: 1000, suffix: "K" },
  ];
  for (const { limit, suffix } of units) {
    if (value >= limit) {
      const scaled = value / limit;
      const text = scaled >= 100 ? String(Math.round(scaled)) : scaled.toFixed(1);
      return `${text.replace(/\.0$/, "")}${suffix}`;
    }
  }
  return String(value);
}

/** Bytes -> a human size like "4.2 MB". Null renders as an empty string. */
export function formatBytes(bytes: number | null | undefined): string {
  if (bytes == null || bytes < 0) {
    return "";
  }
  if (bytes < 1024) {
    return `${bytes} B`;
  }
  const units = ["KB", "MB", "GB", "TB"];
  let value = bytes / 1024;
  let unit = 0;
  while (value >= 1024 && unit < units.length - 1) {
    value /= 1024;
    unit += 1;
  }
  return `${value.toFixed(1)} ${units[unit]}`;
}

/** ISO timestamp -> a locale date like "Jan 2, 2026". Invalid/null renders as an empty string. */
export function formatDate(iso: string | null | undefined): string {
  if (!iso) {
    return "";
  }
  const date = new Date(iso);
  if (Number.isNaN(date.getTime())) {
    return "";
  }
  return date.toLocaleDateString(undefined, { year: "numeric", month: "short", day: "numeric" });
}

/** Seconds -> "m:ss" (or "h:mm:ss"). Null renders as an empty string. */
export function formatDuration(seconds: number | null | undefined): string {
  if (seconds == null || seconds < 0) {
    return "";
  }
  const total = Math.round(seconds);
  const hours = Math.floor(total / 3600);
  const minutes = Math.floor((total % 3600) / 60);
  const secs = total % 60;
  const mm = hours > 0 ? String(minutes).padStart(2, "0") : String(minutes);
  const ss = String(secs).padStart(2, "0");
  return hours > 0 ? `${hours}:${mm}:${ss}` : `${mm}:${ss}`;
}
