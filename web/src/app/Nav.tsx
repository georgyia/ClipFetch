import { useLayoutEffect, useRef, useState } from "react";
import { NavLink, useLocation } from "react-router-dom";
import { Icon } from "../components/Icon";
import styles from "./AppShell.module.css";
import { NAV_ITEMS } from "./navItems";

export interface NavProps {
  variant: "rail" | "tabs";
}

interface Indicator {
  offset: number;
  size: number;
}

/** Primary navigation, rendered as a desktop side rail or a mobile bottom tab bar. */
export function Nav({ variant }: NavProps) {
  const label = variant === "rail" ? "Primary" : "Primary (mobile)";
  const containerClass = variant === "rail" ? styles.nav : styles.tabBar;
  const listRef = useRef<HTMLUListElement>(null);
  const [indicator, setIndicator] = useState<Indicator | null>(null);
  const { pathname } = useLocation();

  /*
   * Which item is active is derived from the route rather than read back out of the DOM, so the
   * indicator has a single source of truth and the effect below only has to measure geometry.
   */
  const activeIndex = NAV_ITEMS.findIndex((item) =>
    item.to === "/" ? pathname === "/" : pathname === item.to || pathname.startsWith(`${item.to}/`),
  );

  /*
   * One indicator element slides between items instead of each item drawing its own, so moving
   * between routes reads as a single continuous object. Geometry is measured with
   * getBoundingClientRect relative to the list, which sidesteps any question about what the
   * offsetParent happens to be, and applied as a transform the compositor can animate for free.
   */
  useLayoutEffect(() => {
    const list = listRef.current;
    if (!list) {
      return;
    }
    const measure = () => {
      const active = list.children[activeIndex];
      if (!active) {
        setIndicator(null);
        return;
      }
      const listBox = list.getBoundingClientRect();
      const box = active.getBoundingClientRect();
      setIndicator(
        variant === "rail"
          ? { offset: box.top - listBox.top, size: box.height }
          : { offset: box.left - listBox.left, size: box.width },
      );
    };
    measure();

    // Re-measure when the rail resizes, or when the font finishes loading and reflows the labels.
    if (typeof ResizeObserver === "undefined") {
      return;
    }
    const observer = new ResizeObserver(measure);
    observer.observe(list);
    return () => observer.disconnect();
  }, [variant, activeIndex]);

  const indicatorStyle = indicator
    ? variant === "rail"
      ? { transform: `translateY(${indicator.offset}px)`, height: `${indicator.size}px` }
      : { transform: `translateX(${indicator.offset}px)`, width: `${indicator.size}px` }
    : undefined;

  return (
    <nav aria-label={label} className={containerClass}>
      <div className={styles.navInner}>
        {indicator ? (
          <span
            aria-hidden="true"
            className={variant === "rail" ? styles.railIndicator : styles.tabIndicator}
            style={indicatorStyle}
          />
        ) : null}
        <ul className={styles.navList} ref={listRef}>
          {NAV_ITEMS.map((item) => (
            <li key={item.to}>
              <NavLink
                to={item.to}
                end={item.to === "/"}
                title={variant === "rail" ? item.hint : undefined}
                className={({ isActive }) =>
                  `${styles.navLink} ${isActive ? styles.navLinkActive : ""}`.trim()
                }
              >
                <span className={styles.navContent}>
                  <span className={styles.navIcon}>
                    <Icon icon={item.icon} size="lg" />
                  </span>
                  <span className={styles.navLabel}>{item.label}</span>
                </span>
              </NavLink>
            </li>
          ))}
        </ul>
      </div>
    </nav>
  );
}
