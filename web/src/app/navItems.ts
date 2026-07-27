import { Icons, type LucideIcon } from "../components/icons";

// Single source of truth for primary navigation, shared by the desktop rail and the mobile tab bar.
export interface NavItem {
  to: string;
  label: string;
  icon: LucideIcon;
  /** One-line purpose, surfaced as the rail tooltip and in the command palette. */
  hint: string;
}

export const NAV_ITEMS: readonly NavItem[] = [
  { to: "/", label: "Home", icon: Icons.home, hint: "Featured clip and your rails" },
  { to: "/explore", label: "Explore", icon: Icons.explore, hint: "Filter the library by facet" },
  { to: "/search", label: "Search", icon: Icons.search, hint: "Find clips by text or meaning" },
  { to: "/library", label: "Library", icon: Icons.library, hint: "Manage libraries and folders" },
  { to: "/downloads", label: "Downloads", icon: Icons.downloads, hint: "Add reels and watch jobs" },
  { to: "/settings", label: "Settings", icon: Icons.settings, hint: "Theme, diagnostics, account" },
];
