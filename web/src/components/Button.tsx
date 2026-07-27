import type { ButtonHTMLAttributes, ReactNode } from "react";
import styles from "./Button.module.css";
import { Icon } from "./Icon";
import { Icons, type LucideIcon } from "./icons";

export type ButtonVariant = "primary" | "secondary" | "ghost" | "subtle" | "destructive";
export type ButtonSize = "sm" | "md" | "lg";

export interface ButtonProps extends ButtonHTMLAttributes<HTMLButtonElement> {
  variant?: ButtonVariant;
  size?: ButtonSize;
  /** Leading icon from the shared vocabulary; swapped for a spinner while `loading`. */
  icon?: LucideIcon;
  /** Trailing icon — chevrons, external-link marks, and other "what happens next" hints. */
  iconAfter?: LucideIcon;
  /**
   * Shows a spinner in place of the leading icon and blocks input, without collapsing the
   * button's width — the label stays put so the row doesn't reflow mid-action.
   */
  loading?: boolean;
  /** Square icon-only button. The caller must supply `aria-label` for a usable name. */
  iconOnly?: boolean;
  children?: ReactNode;
}

const ICON_SIZE = { sm: "sm", md: "sm", lg: "md" } as const;

/**
 * The one button in the system. Variants map to intent, not to colour:
 *   primary      the single most important action on a surface (gradient, glows on hover)
 *   secondary    common actions that sit beside a primary
 *   subtle       low-emphasis actions inside dense rows and toolbars
 *   ghost        chrome-level actions where a filled box would be visual noise
 *   destructive  removals and disconnects
 */
export function Button({
  variant = "secondary",
  size = "md",
  icon,
  iconAfter,
  loading = false,
  iconOnly = false,
  className,
  type,
  disabled,
  children,
  ...rest
}: ButtonProps) {
  const classes = [
    styles.button,
    styles[variant],
    styles[size],
    iconOnly ? styles.iconOnly : null,
    className,
  ]
    .filter(Boolean)
    .join(" ");

  const leading = loading ? Icons.spinner : icon;

  return (
    <button
      type={type ?? "button"}
      className={classes}
      disabled={disabled || loading}
      aria-busy={loading || undefined}
      {...rest}
    >
      {leading ? (
        <Icon
          icon={leading}
          size={ICON_SIZE[size]}
          className={loading ? styles.spinner : undefined}
        />
      ) : null}
      {children ? <span className={styles.label}>{children}</span> : null}
      {iconAfter && !loading ? <Icon icon={iconAfter} size={ICON_SIZE[size]} /> : null}
    </button>
  );
}
