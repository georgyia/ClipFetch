import styles from "./Skeleton.module.css";

export interface SkeletonProps {
  width?: string;
  height?: string;
  radius?: string;
  className?: string;
}

/**
 * A single shimmering placeholder block.
 *
 * All skeletons are `aria-hidden`: the *container* announces loading through one live region, so a
 * screen reader hears "Loading your library" once rather than a stream of anonymous placeholders.
 */
export function Skeleton({ width, height, radius, className }: SkeletonProps) {
  return (
    <span
      className={[styles.skeleton, className].filter(Boolean).join(" ")}
      style={{ width, height, borderRadius: radius }}
      aria-hidden="true"
    />
  );
}
