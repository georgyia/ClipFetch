import { useId } from "react";
import styles from "./BrandMark.module.css";

export interface BrandMarkProps {
  size?: number;
  className?: string;
}

/**
 * The ClipFetch Watch mark: a portrait frame — the 9:16 shape the whole product is built around —
 * with a play triangle punched clean through it, washed in the signature coral→violet gradient.
 *
 * Drawn as inline SVG rather than a Unicode glyph (the old `◐`) so it renders identically on every
 * platform and can carry the gradient. The gradient id is per-instance, so several marks on one
 * page never collide in the SVG id namespace.
 */
export function BrandMark({ size = 26, className }: BrandMarkProps) {
  const gradientId = useId();
  return (
    <svg
      className={[styles.mark, className].filter(Boolean).join(" ")}
      width={size}
      height={size}
      viewBox="0 0 24 24"
      aria-hidden="true"
      focusable="false"
    >
      <defs>
        <linearGradient id={gradientId} x1="0" y1="0" x2="1" y2="1">
          <stop offset="0%" stopColor="var(--color-accent-pressed)" />
          <stop offset="55%" stopColor="var(--color-accent)" />
          <stop offset="100%" stopColor="var(--color-accent-violet)" />
        </linearGradient>
      </defs>
      {/*
        Outer squircle and the inner triangle are one path with evenodd fill, so the triangle is a
        true hole: whatever sits behind the mark shows through it.
      */}
      <path
        fill={`url(#${gradientId})`}
        fillRule="evenodd"
        d="M7.6 1.75h8.8a5.85 5.85 0 0 1 5.85 5.85v8.8a5.85 5.85 0 0 1-5.85 5.85H7.6a5.85 5.85 0 0 1-5.85-5.85V7.6A5.85 5.85 0 0 1 7.6 1.75Zm2.44 5.62a.9.9 0 0 0-1.36.78v7.7a.9.9 0 0 0 1.36.77l6.42-3.85a.9.9 0 0 0 0-1.55l-6.42-3.85Z"
      />
    </svg>
  );
}
