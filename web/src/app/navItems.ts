// Single source of truth for primary navigation, shared by the desktop rail and the mobile tab bar.
export interface NavItem {
  to: string;
  label: string;
  icon: string;
}

export const NAV_ITEMS: readonly NavItem[] = [
  { to: "/", label: "Home", icon: "⌂" },
  { to: "/explore", label: "Explore", icon: "▤" },
  { to: "/search", label: "Search", icon: "⌕" },
  { to: "/library", label: "Library", icon: "▦" },
  { to: "/downloads", label: "Downloads", icon: "↓" },
  { to: "/settings", label: "Settings", icon: "⚙" },
];
