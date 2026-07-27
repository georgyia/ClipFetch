import type { ReactNode } from "react";
import { Link } from "react-router-dom";
import { BrandMark } from "../components/BrandMark";
import { ThemeToggle } from "../components/ThemeToggle";
import { useScrolled } from "../lib/useScrolled";
import styles from "./AppShell.module.css";
import { LibrarySelector } from "./LibrarySelector";
import { Nav } from "./Nav";
import { RouteAnnouncer } from "./RouteAnnouncer";

export interface AppShellProps {
  children: ReactNode;
}

/**
 * Application chrome: a scroll-aware glass header, adaptive navigation (rail on desktop, tabs on
 * mobile), and the ambient page wash behind it all.
 *
 * The header is transparent at the top of a page so a hero runs clean under it, and condenses into
 * frosted glass with a hairline border once content scrolls beneath — chrome that gets out of the
 * way of the content, then reasserts itself when it needs to stay legible.
 */
export function AppShell({ children }: AppShellProps) {
  const scrolled = useScrolled();

  return (
    <div className={styles.shell}>
      <a className="skip-link" href="#main">
        Skip to content
      </a>
      <RouteAnnouncer />
      <header className={styles.header} data-condensed={scrolled}>
        <Link to="/" className={styles.brand}>
          <BrandMark />
          <span className={styles.brandName}>
            ClipFetch <span className={styles.brandSuffix}>Watch</span>
          </span>
        </Link>
        <div className={styles.headerSpacer} />
        <ThemeToggle compact />
        <LibrarySelector />
      </header>
      <div className={styles.body}>
        <Nav variant="rail" />
        <main id="main" className={styles.content}>
          {children}
        </main>
      </div>
      <Nav variant="tabs" />
    </div>
  );
}
