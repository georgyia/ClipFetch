import { type ReactNode, useMemo, useState } from "react";
import { useTranscript } from "../api/queries";
import type { ClipDetail } from "../api/types";
import { Button } from "./Button";
import { Icon } from "./Icon";
import styles from "./TranscriptPanel.module.css";
import { Icons } from "./icons";

export interface TranscriptPanelProps {
  clip: ClipDetail;
}

/**
 * What the enricher's status means, in the user's terms.
 *
 * The stored error string is never sent to us — it can name local paths — so the status *is* the
 * explanation, and each one has to say something true and useful on its own.
 */
const STATUS_NOTE: Record<string, string> = {
  silent: "Transcribed, but no speech was found in this clip.",
  unsupported: "This clip's audio could not be read by the transcriber.",
  failed: "Transcription did not finish. Running it again is safe.",
};

/** Split text on a query, keeping the matches, so they can be marked without dangerous HTML. */
export function splitOnQuery(text: string, query: string): { text: string; match: boolean }[] {
  const needle = query.trim().toLowerCase();
  if (!needle) {
    return [{ text, match: false }];
  }
  const parts: { text: string; match: boolean }[] = [];
  const haystack = text.toLowerCase();
  let cursor = 0;
  for (;;) {
    const at = haystack.indexOf(needle, cursor);
    if (at === -1) {
      break;
    }
    if (at > cursor) {
      parts.push({ text: text.slice(cursor, at), match: false });
    }
    parts.push({ text: text.slice(at, at + needle.length), match: true });
    cursor = at + needle.length;
  }
  if (cursor < text.length) {
    parts.push({ text: text.slice(cursor), match: false });
  }
  return parts;
}

/**
 * A clip's transcript, with its provenance, a copy action, and find-within.
 *
 * Text search already indexes transcripts, so a clip can match on words that were, until now,
 * never shown anywhere in the app. This is where you read them.
 *
 * The panel renders nothing at all for a clip that was never transcribed: an empty box announcing
 * an absent feature is worse than silence.
 */
export function TranscriptPanel({ clip }: TranscriptPanelProps) {
  const [open, setOpen] = useState(false);
  const [query, setQuery] = useState("");
  const [copied, setCopied] = useState(false);
  // Only fetch the body once the panel is actually opened.
  const transcript = useTranscript(clip.id, open);

  const text = transcript.data?.text ?? "";
  const segments = useMemo(() => splitOnQuery(text, query), [text, query]);
  const matches = segments.filter((part) => part.match).length;

  if (!clip.has_transcript && !clip.transcript_status) {
    return null;
  }

  async function copy() {
    try {
      await navigator.clipboard.writeText(text);
      setCopied(true);
      window.setTimeout(() => setCopied(false), 2000);
    } catch {
      setCopied(false);
    }
  }

  const note = clip.transcript_status ? STATUS_NOTE[clip.transcript_status] : undefined;

  return (
    <section className={styles.panel} aria-label="Transcript">
      <div className={styles.head}>
        <h2 className={styles.title}>
          <Icon icon={Icons.comments} size="sm" />
          Transcript
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
        <Body
          loading={transcript.isLoading}
          error={transcript.isError}
          empty={!text}
          meta={
            transcript.data ? (
              <p className={styles.meta}>
                {transcript.data.language ? `${transcript.data.language} · ` : ""}
                {transcript.data.character_count.toLocaleString()} characters
                {transcript.data.model_id ? ` · ${transcript.data.model_id}` : ""}
                {transcript.data.model_revision ? ` (${transcript.data.model_revision})` : ""}
              </p>
            ) : null
          }
        >
          <div className={styles.tools}>
            <label className="visually-hidden" htmlFor="transcript-find">
              Find in transcript
            </label>
            <input
              id="transcript-find"
              className={styles.find}
              type="search"
              placeholder="Find in transcript"
              value={query}
              onChange={(event) => setQuery(event.target.value)}
            />
            {query.trim() ? (
              <p className={styles.matches} aria-live="polite">
                {matches === 0 ? "No matches" : `${matches} match${matches === 1 ? "" : "es"}`}
              </p>
            ) : null}
            <Button
              variant="subtle"
              size="sm"
              icon={copied ? Icons.confirm : Icons.bookmark}
              onClick={copy}
            >
              {copied ? "Copied" : "Copy"}
            </Button>
          </div>

          <p className={styles.body}>
            {segments.map((part, index) =>
              part.match ? (
                // biome-ignore lint/suspicious/noArrayIndexKey: segments are positional by nature
                <mark key={index} className={styles.mark}>
                  {part.text}
                </mark>
              ) : (
                // biome-ignore lint/suspicious/noArrayIndexKey: segments are positional by nature
                <span key={index}>{part.text}</span>
              ),
            )}
          </p>

          {transcript.data?.truncated ? (
            <p className={styles.note}>
              Showing the first {text.length.toLocaleString()} characters of a longer transcript.
            </p>
          ) : null}
        </Body>
      ) : null}
    </section>
  );
}

function Body({
  loading,
  error,
  empty,
  meta,
  children,
}: {
  loading: boolean;
  error: boolean;
  empty: boolean;
  meta: ReactNode;
  children: ReactNode;
}) {
  if (loading) {
    return <p className={styles.note}>Loading the transcript…</p>;
  }
  if (error) {
    return (
      <p className={styles.note} role="alert">
        The transcript could not be loaded.
      </p>
    );
  }
  if (empty) {
    return <p className={styles.note}>There is no transcript text for this clip.</p>;
  }
  return (
    <>
      {meta}
      {children}
    </>
  );
}
