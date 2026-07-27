import { Badge, type BadgeTone } from "./Badge";
import { Icons } from "./icons";

export interface QualityBadgeProps {
  /** Tier slug from the probed media block: unknown | sd | hd | full_hd | uhd. */
  tier: string;
  /** Human label; falls back to a slug-derived label. */
  label?: string;
  /** Why this tier was assigned (e.g. "1080x1920 source"); shown as a tooltip. */
  reason?: string;
}

const FALLBACK_LABELS: Record<string, string> = {
  unknown: "Unknown",
  sd: "SD",
  hd: "HD",
  full_hd: "Full HD",
  uhd: "4K",
};

/**
 * Tone encodes the tier so quality is legible at a glance: the good tiers read as positive, SD as
 * a caution, and an unprobed file stays neutral rather than implying a verdict it doesn't have.
 */
const TONES: Record<string, BadgeTone> = {
  unknown: "neutral",
  sd: "warning",
  hd: "info",
  full_hd: "success",
  uhd: "violet",
};

// A technical-quality badge measured from the probed file — distinct from a download preference.
export function QualityBadge({ tier, label, reason }: QualityBadgeProps) {
  const text = label ?? FALLBACK_LABELS[tier] ?? "Unknown";
  return (
    <Badge
      tone={TONES[tier] ?? "neutral"}
      icon={Icons.quality}
      title={reason ?? `Quality: ${text}`}
    >
      {text}
    </Badge>
  );
}
