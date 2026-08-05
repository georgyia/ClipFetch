import styles from "./ExportMenu.module.css";
import { Icon } from "./Icon";
import { Icons } from "./icons";

export interface ExportMenuProps {
  /** The export endpoint with its filters already applied, minus `format`. */
  path: string;
  /** How many clips this view holds, so the choice is made with the size in view. */
  count: number;
}

function withFormat(path: string, format: string): string {
  return `${path}${path.includes("?") ? "&" : "?"}format=${format}`;
}

/**
 * Download the current view as a playlist or a manifest.
 *
 * Plain links rather than fetch-and-blob: a GET that returns `Content-Disposition: attachment` is
 * already a download, and letting the browser own it means real progress, a real Save dialog, and
 * no copy of the file in JS memory.
 *
 * `<details>` gives keyboard operation, Escape, and click-outside semantics from the platform, so
 * this needs no focus trap of its own.
 */
export function ExportMenu({ path, count }: ExportMenuProps) {
  return (
    <details className={styles.menu}>
      <summary className={styles.trigger}>
        <Icon icon={Icons.downloads} size="sm" />
        Export
      </summary>
      <div className={styles.panel}>
        <p className={styles.count}>
          {count} clip{count === 1 ? "" : "s"} in this view
        </p>
        <a className={styles.option} href={withFormat(path, "m3u")} download>
          <Icon icon={Icons.queue} size="sm" />
          <span>
            <strong>Playlist</strong>
            <small>.m3u — opens in VLC or mpv</small>
          </span>
        </a>
        <a className={styles.option} href={withFormat(path, "json")} download>
          <Icon icon={Icons.clip} size="sm" />
          <span>
            <strong>Manifest</strong>
            <small>.json — metadata for every clip</small>
          </span>
        </a>
        <p className={styles.note}>Both use library-relative paths, so they stay portable.</p>
      </div>
    </details>
  );
}
