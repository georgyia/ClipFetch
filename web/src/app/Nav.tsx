import { NavLink } from "react-router-dom";
import styles from "./AppShell.module.css";
import { NAV_ITEMS } from "./navItems";

export interface NavProps {
  variant: "rail" | "tabs";
}

/** Primary navigation, rendered as a desktop side rail or a mobile bottom tab bar. */
export function Nav({ variant }: NavProps) {
  const label = variant === "rail" ? "Primary" : "Primary (mobile)";
  const containerClass = variant === "rail" ? styles.nav : styles.tabBar;
  return (
    <nav aria-label={label} className={containerClass}>
      <ul className={styles.navList}>
        {NAV_ITEMS.map((item) => (
          <li key={item.to}>
            <NavLink
              to={item.to}
              end={item.to === "/"}
              className={({ isActive }) =>
                `${styles.navLink} ${isActive ? styles.navLinkActive : ""}`.trim()
              }
            >
              <span className={styles.navIcon} aria-hidden="true">
                {item.icon}
              </span>
              <span>{item.label}</span>
            </NavLink>
          </li>
        ))}
      </ul>
    </nav>
  );
}
