import { NavLink } from "react-router-dom";

const LINKS: ReadonlyArray<readonly [string, string]> = [
  ["/", "Home"],
  ["/explore", "Explore"],
  ["/search", "Search"],
  ["/library", "Library"],
  ["/downloads", "Downloads"],
  ["/settings", "Settings"],
];

export function PrimaryNav() {
  return (
    <nav aria-label="Primary">
      <ul>
        {LINKS.map(([to, label]) => (
          <li key={to}>
            <NavLink to={to} end={to === "/"}>
              {label}
            </NavLink>
          </li>
        ))}
      </ul>
    </nav>
  );
}
