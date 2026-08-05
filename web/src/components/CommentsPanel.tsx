import { useState } from "react";
import { useComments } from "../api/queries";
import type { ClipDetail } from "../api/types";
import { formatDate } from "../lib/format";
import { Button } from "./Button";
import styles from "./CommentsPanel.module.css";
import { Icon } from "./Icon";
import { Icons } from "./icons";

export interface CommentsPanelProps {
  clip: ClipDetail;
}

/**
 * What a non-complete capture status means. As with transcripts, the stored error string never
 * leaves the server, so the status carries the whole explanation.
 */
const STATUS_NOTE: Record<string, string> = {
  empty: "Comments were fetched, but this clip had none to keep.",
  disabled: "The creator has comments turned off for this clip.",
  deleted: "The original post is gone, so its comments could not be fetched.",
  unavailable: "The original post could not be reached when comments were fetched.",
  "authentication-checkpoint": "Instagram asked for a sign-in check during the last fetch.",
  "rate-limited": "Instagram rate-limited the last fetch. Trying later usually works.",
  skipped: "This clip was skipped by the last comment fetch.",
  failed: "The last comment fetch did not finish.",
};

/**
 * A clip's captured comments.
 *
 * These are a **snapshot** taken when `library enrich comments` ran, not a live view — the capture
 * time is shown for exactly that reason. Comment text is third-party content and is rendered as
 * text, never as markup.
 */
export function CommentsPanel({ clip }: CommentsPanelProps) {
  const [open, setOpen] = useState(false);
  const comments = useComments(clip.id, open);

  if (!clip.has_comments && !clip.comment_status) {
    return null;
  }

  const note = clip.comment_status ? STATUS_NOTE[clip.comment_status] : undefined;
  const captured = formatDate(comments.data?.retrieved_at ?? null);

  return (
    <section className={styles.panel} aria-label="Comments">
      <div className={styles.head}>
        <h2 className={styles.title}>
          <Icon icon={Icons.comments} size="sm" />
          Comments
        </h2>
        <Button
          variant="subtle"
          size="sm"
          icon={open ? Icons.chevronDown : Icons.chevronRight}
          aria-expanded={open}
          onClick={() => setOpen((previous) => !previous)}
        >
          {open ? "Hide" : "Show"}
        </Button>
      </div>

      {note ? <p className={styles.note}>{note}</p> : null}

      {open ? (
        <>
          {comments.isLoading ? <p className={styles.note}>Loading comments…</p> : null}
          {comments.isError ? (
            <p className={styles.note} role="alert">
              The comments could not be loaded.
            </p>
          ) : null}

          {comments.data ? (
            <>
              <p className={styles.note}>
                {comments.data.total === 0
                  ? "No comments were kept for this clip."
                  : `${comments.data.total} kept${captured ? ` · captured ${captured}` : ""}`}
                {comments.data.total > 0
                  ? " — a local snapshot from when they were fetched, not a live view."
                  : ""}
              </p>
              {comments.data.items.length > 0 ? (
                <ul className={styles.list}>
                  {comments.data.items.map((comment) => (
                    <li key={comment.id} className={styles.item}>
                      {comment.text}
                    </li>
                  ))}
                </ul>
              ) : null}
              {comments.data.next_offset != null ? (
                <p className={styles.note}>
                  Showing the first {comments.data.items.length} of {comments.data.total}.
                </p>
              ) : null}
            </>
          ) : null}
        </>
      ) : null}
    </section>
  );
}
