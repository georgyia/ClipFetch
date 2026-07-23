import type { ReactNode } from "react";
import { Link } from "react-router-dom";
import styles from "./AppShell.module.css";
import { LibrarySelector } from "./LibrarySelector";
import { Nav } from "./Nav";
import { RouteAnnouncer } from "./RouteAnnouncer";

export interface AppShellProps {
  children: ReactNode;
}

/** Application chrome: sticky header, adaptive navigation (rail on desktop, tabs on mobile). */
export function AppShell({ children }: AppShellProps) {
  return (
    <div className={styles.shell}>
      <a className="skip-link" href="#main">
        Skip to content
      </a>
      <RouteAnnouncer />
      <header className={styles.header}>
        <Link to="/" className={styles.brand}>
          <span className={styles.brandMark}>◐</span> ClipFetch <span>Watch</span>
        </Link>
        <div className={styles.headerSpacer} />
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
