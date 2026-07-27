import styles from "./Icon.module.css";
import type { LucideIcon } from "./icons";

/**
 * Optical sizes. Icons are drawn on a 24px grid, so these are the sizes where lucide's 1.5px
 * stroke stays crisp rather than blurring between device pixels.
 */
export type IconSize = "xs" | "sm" | "md" | "lg" | "xl";

const SIZES: Record<IconSize, number> = {
  xs: 14,
  sm: 16,
  md: 18,
  lg: 22,
  xl: 28,
};

/** Thinner strokes at large sizes keep the apparent weight even across the scale. */
const STROKE: Record<IconSize, number> = {
  xs: 2,
  sm: 1.9,
  md: 1.8,
  lg: 1.7,
  xl: 1.6,
};

export interface IconProps {
  icon: LucideIcon;
  size?: IconSize;
  /**
   * Only pass this when the icon is the *sole* carrier of meaning — an icon-only button with no
   * adjacent text. When it sits next to a visible label, leave it off: the icon is decorative and
   * is hidden from assistive tech so the label isn't announced twice.
   */
  label?: string;
  /** Fills from `currentColor` by default; set to tint the glyph independently of its text. */
  className?: string;
  strokeWidth?: number;
}

/**
 * The single entry point for iconography. Enforces the sizing ramp, the stroke convention, and
 * the decorative-by-default accessibility rule so no call site has to remember them.
 */
export function Icon({ icon: Glyph, size = "md", label, className, strokeWidth }: IconProps) {
  const classes = [styles.icon, className].filter(Boolean).join(" ");
  return (
    <Glyph
      className={classes}
      size={SIZES[size]}
      strokeWidth={strokeWidth ?? STROKE[size]}
      absoluteStrokeWidth
      aria-hidden={label ? undefined : true}
      role={label ? "img" : undefined}
      aria-label={label}
      focusable="false"
    />
  );
}
