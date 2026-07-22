// Small presentation helpers shared across cards, rails, and the detail page.

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
