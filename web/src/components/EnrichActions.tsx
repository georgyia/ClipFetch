import { useQueryClient } from "@tanstack/react-query";
import { useEffect, useState } from "react";
import { ApiError } from "../api/client";
import { useEnrichClip, useJobs } from "../api/queries";
import type { ClipDetail, Job } from "../api/types";
import { Button } from "./Button";
import styles from "./EnrichActions.module.css";
import { useToast } from "./Toast";
import { Icons } from "./icons";

export interface EnrichActionsProps {
  clip: ClipDetail;
}

type Target = "transcript" | "comments";

/** What a failed enrichment means, and what the user can actually do about it. */
const RECOVERY: Record<string, string> = {
  transcription_unavailable:
    'Local transcription is not installed. Run: pip install "clipfetch[transcribe]"',
  authentication_required: "Connect your Instagram account in Settings, then try again.",
  unsupported_source: "Comments can only be fetched for Instagram clips.",
  clip_not_found: "This clip is no longer in the library.",
};

/**
 * Ask for a transcript or comments without leaving the clip.
 *
 * The enrichment runs as a real job — the same queue as downloads, with leases, progress, retries,
 * and cancellation — so this component only starts one and follows it. When the job lands, the
 * clip's cached detail and its panels are invalidated, so the result appears in place rather than
 * after a reload.
 */
export function EnrichActions({ clip }: EnrichActionsProps) {
  const enrich = useEnrichClip();
  const jobs = useJobs();
  const queryClient = useQueryClient();
  const toast = useToast();
  const [watching, setWatching] = useState<{ id: string; target: Target } | null>(null);
  const [error, setError] = useState<string | null>(null);

  const job: Job | undefined = watching
    ? jobs.data?.jobs.find((item) => item.id === watching.id)
    : undefined;

  useEffect(() => {
    if (!watching || !job) {
      return;
    }
    if (job.state === "succeeded") {
      toast(watching.target === "transcript" ? "Transcript added." : "Comments fetched.", {
        variant: "success",
      });
      // The panels read their own endpoints, so refresh the clip and both bodies.
      queryClient.invalidateQueries({ queryKey: ["clip", clip.id] });
      queryClient.invalidateQueries({ queryKey: ["transcript", clip.id] });
      queryClient.invalidateQueries({ queryKey: ["comments", clip.id] });
      setWatching(null);
    } else if (job.state === "failed" || job.state === "cancelled") {
      const code = job.error?.code ?? "";
      setError(RECOVERY[code] ?? job.error?.message ?? "That enrichment did not finish.");
      setWatching(null);
    }
  }, [job, watching, clip.id, queryClient, toast]);

  async function start(target: Target) {
    setError(null);
    try {
      const started = await enrich.mutateAsync({ clipId: clip.id, target });
      setWatching({ id: started.id, target });
    } catch (err) {
      if (err instanceof ApiError) {
        // A refused prerequisite arrives here rather than as a failed job — say what to install.
        setError(RECOVERY[err.code] ?? err.message);
      } else {
        setError("Could not start that enrichment.");
      }
    }
  }

  const running = watching !== null || enrich.isPending;
  const phase = job?.phase ? ` — ${job.phase}` : "";
  const needsTranscript = !clip.has_transcript;
  const needsComments = !clip.has_comments;

  if (!needsTranscript && !needsComments) {
    return null;
  }

  return (
    <div className={styles.actions}>
      {needsTranscript ? (
        <Button
          variant="subtle"
          size="sm"
          icon={Icons.sparkle}
          loading={running && watching?.target === "transcript"}
          disabled={running}
          onClick={() => start("transcript")}
        >
          Add transcript
        </Button>
      ) : null}
      {needsComments ? (
        <Button
          variant="subtle"
          size="sm"
          icon={Icons.comments}
          loading={running && watching?.target === "comments"}
          disabled={running}
          onClick={() => start("comments")}
        >
          Fetch comments
        </Button>
      ) : null}

      {watching ? (
        <p className={styles.status} aria-live="polite">
          {job?.state === "running" ? `Working${phase}` : "Queued"}…
        </p>
      ) : null}
      {error ? (
        <p className={styles.error} role="alert">
          {error}
        </p>
      ) : null}
    </div>
  );
}
