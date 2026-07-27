import { type ThemeChoice, useTheme } from "../lib/theme";
import { Icon } from "./Icon";
import styles from "./ThemeToggle.module.css";
import { Icons, type LucideIcon } from "./icons";

const OPTIONS: Array<{ value: ThemeChoice; label: string; icon: LucideIcon }> = [
  { value: "system", label: "System", icon: Icons.themeSystem },
  { value: "light", label: "Light", icon: Icons.themeLight },
  { value: "dark", label: "Dark", icon: Icons.themeDark },
];

export interface ThemeToggleProps {
  /** Icon-only rendering for the header; the full labelled control is used in Settings. */
  compact?: boolean;
}

/**
 * A three-state segmented control rather than a two-state switch: "System" is a real choice, and a
 * binary toggle would silently strand a user who wants the app to follow their OS.
 *
 * Built from radios so arrow keys move between options natively and screen readers announce it as
 * one named group with a selected member.
 */
export function ThemeToggle({ compact = false }: ThemeToggleProps) {
  const { choice, resolved, setChoice } = useTheme();

  return (
    <fieldset className={[styles.group, compact ? styles.compact : null].filter(Boolean).join(" ")}>
      <legend className="visually-hidden">Colour theme</legend>
      {/* The moving pill is a sibling, positioned by index, so it slides between options. */}
      <span
        className={styles.indicator}
        style={{ "--index": OPTIONS.findIndex((o) => o.value === choice) } as React.CSSProperties}
        aria-hidden="true"
      />
      {OPTIONS.map((option) => (
        <label key={option.value} className={styles.option}>
          <input
            type="radio"
            name="clipfetch-theme"
            value={option.value}
            className={styles.input}
            checked={choice === option.value}
            onChange={() => setChoice(option.value)}
          />
          <Icon icon={option.icon} size="sm" />
          <span className={compact ? "visually-hidden" : styles.label}>
            {option.label}
            {option.value === "system" ? ` (${resolved})` : ""}
          </span>
        </label>
      ))}
    </fieldset>
  );
}
