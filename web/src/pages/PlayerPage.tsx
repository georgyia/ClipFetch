import { useCallback, useEffect, useRef, useState } from "react";
import { useNavigate, useParams } from "react-router-dom";
import { useClipDetail, useClipList, usePlayback, useSavePlayback } from "../api/queries";
import { mediaUrl } from "../api/types";
import { formatDuration } from "../lib/format";
import styles from "./PlayerPage.module.css";

// Persist progress at most this often while playing; also flushed on pause, end, and unmount.
const SAVE_INTERVAL_MS = 5000;

/**
 * Vertical player MVP. Streams media by clip id (the backend serves byte ranges), with custom
 * controls, a keyboard map, and prev/next queue navigation over the recent-clips list.
 *
 * This is the browser counterpart to the shipping terminal player in clipfetch/watcher.py: both
 * resolve a clip and play its local media, but the terminal player hands off to the OS player while
 * this one plays inline.
 */
export function PlayerPage() {
  const { id = "" } = useParams();
  const navigate = useNavigate();
  const videoRef = useRef<HTMLVideoElement>(null);

  const { data: clip } = useClipDetail(id);
  const playback = usePlayback(id);
  const save = useSavePlayback();
  const queue = useClipList(["clips", "recent"], (cursor) => {
    const params = new URLSearchParams({ limit: "50", sort: "date" });
    if (cursor) {
      params.set("cursor", cursor);
    }
    return `/api/v1/clips?${params.toString()}`;
  });

  const order = (queue.data?.pages.flatMap((page) => page.items) ?? []).filter(
    (item) => item.available,
  );
  const index = order.findIndex((item) => item.id === id);
  const prevId = index > 0 ? order[index - 1].id : null;
  const nextId = index >= 0 && index < order.length - 1 ? order[index + 1].id : null;

  const [playing, setPlaying] = useState(true);
  const [muted, setMuted] = useState(false);
  const [current, setCurrent] = useState(0);
  const [duration, setDuration] = useState(0);
  const [failed, setFailed] = useState(false);

  // Latest progress in seconds, plus bookkeeping for throttled/idempotent writes.
  const progressRef = useRef({ position: 0, duration: 0 });
  const lastSaveRef = useRef(0);
  const hasResumedRef = useRef(false);
  const saveMutateRef = useRef(save.mutate);
  saveMutateRef.current = save.mutate;

  const flushNow = useCallback(
    (completed?: boolean) => {
      const { position, duration: dur } = progressRef.current;
      if (position <= 0 && !completed) {
        return;
      }
      lastSaveRef.current = Date.now();
      saveMutateRef.current({
        clipId: id,
        positionMs: position * 1000,
        durationMs: dur > 0 ? dur * 1000 : null,
        completed,
      });
    },
    [id],
  );

  const togglePlay = useCallback(() => {
    setPlaying((prev) => {
      const next = !prev;
      const video = videoRef.current;
      if (video) {
        if (next) {
          void video.play();
        } else {
          video.pause();
          flushNow(false);
        }
      }
      return next;
    });
  }, [flushNow]);

  const seekBy = useCallback((delta: number) => {
    const video = videoRef.current;
    if (!video) {
      return;
    }
    video.currentTime = Math.max(0, Math.min(video.duration || 0, video.currentTime + delta));
  }, []);

  const goTo = useCallback(
    (clipId: string | null) => {
      if (clipId) {
        navigate(`/watch/${encodeURIComponent(clipId)}`);
      }
    },
    [navigate],
  );

  // Keyboard map. Ignored while a form control has focus.
  useEffect(() => {
    function onKey(event: KeyboardEvent) {
      const target = event.target as HTMLElement | null;
      if (target && /^(INPUT|TEXTAREA|SELECT)$/.test(target.tagName)) {
        return;
      }
      switch (event.key) {
        case " ":
        case "k":
          event.preventDefault();
          togglePlay();
          break;
        case "ArrowRight":
          seekBy(5);
          break;
        case "ArrowLeft":
          seekBy(-5);
          break;
        case "m":
          setMuted((value) => !value);
          break;
        case "n":
          goTo(nextId);
          break;
        case "p":
          goTo(prevId);
          break;
        case "Escape":
          navigate(-1);
          break;
        default:
          break;
      }
    }
    window.addEventListener("keydown", onKey);
    return () => window.removeEventListener("keydown", onKey);
  }, [togglePlay, seekBy, goTo, nextId, prevId, navigate]);

  // Reset transient state and per-clip progress bookkeeping when the clip changes.
  // biome-ignore lint/correctness/useExhaustiveDependencies: id is the intended reset trigger
  useEffect(() => {
    setPlaying(true);
    setFailed(false);
    setCurrent(0);
    progressRef.current = { position: 0, duration: 0 };
    lastSaveRef.current = 0;
    hasResumedRef.current = false;
  }, [id]);

  // Resume from the stored position once both metadata and playback state are available.
  useEffect(() => {
    const video = videoRef.current;
    const resumeMs = playback.data?.playback?.resume_position_ms ?? 0;
    if (video && duration > 0 && resumeMs > 0 && !hasResumedRef.current) {
      hasResumedRef.current = true;
      video.currentTime = resumeMs / 1000;
    }
  }, [playback.data, duration]);

  // Flush the final position when leaving a clip (navigation or closing the player).
  useEffect(() => {
    const clipId = id;
    return () => {
      const { position, duration: dur } = progressRef.current;
      if (position > 0) {
        saveMutateRef.current({
          clipId,
          positionMs: position * 1000,
          durationMs: dur > 0 ? dur * 1000 : null,
        });
      }
    };
  }, [id]);

  const title = clip?.caption?.trim() || clip?.author || "Now playing";

  return (
    <section className={styles.stage} aria-label="Player">
      <div className={styles.topBar}>
        <button
          type="button"
          className={styles.close}
          onClick={() => navigate(-1)}
          aria-label="Close player"
        >
          ✕
        </button>
        <h1 className={styles.heading}>{title}</h1>
      </div>

      <div className={styles.viewport}>
        <video
          ref={videoRef}
          className={styles.video}
          src={mediaUrl(id)}
          autoPlay
          muted={muted}
          playsInline
          onLoadedMetadata={(event) => setDuration(event.currentTarget.duration || 0)}
          onTimeUpdate={(event) => {
            const video = event.currentTarget;
            setCurrent(video.currentTime);
            progressRef.current = { position: video.currentTime, duration: video.duration || 0 };
            const now = Date.now();
            if (playing && now - lastSaveRef.current > SAVE_INTERVAL_MS) {
              flushNow(false);
            }
          }}
          onEnded={() => {
            flushNow(true);
            if (nextId) {
              goTo(nextId);
            } else {
              setPlaying(false);
            }
          }}
          onError={() => setFailed(true)}
        />
        {failed ? (
          <p className={styles.overlayMessage}>
            This clip could not be played. The media file may be missing.
          </p>
        ) : null}
      </div>

      <div className={styles.controls}>
        <input
          className={styles.scrubber}
          type="range"
          min={0}
          max={duration || 0}
          step={0.1}
          value={Math.min(current, duration || 0)}
          onChange={(event) => {
            const video = videoRef.current;
            if (video) {
              video.currentTime = Number(event.target.value);
            }
          }}
          aria-label="Seek"
        />
        <div className={styles.buttons}>
          <button
            type="button"
            className={styles.iconButton}
            onClick={() => goTo(prevId)}
            disabled={!prevId}
            aria-label="Previous clip"
          >
            ⏮
          </button>
          <button
            type="button"
            className={styles.iconButton}
            onClick={togglePlay}
            aria-label={playing ? "Pause" : "Play"}
          >
            {playing ? "⏸" : "▶"}
          </button>
          <button
            type="button"
            className={styles.iconButton}
            onClick={() => goTo(nextId)}
            disabled={!nextId}
            aria-label="Next clip"
          >
            ⏭
          </button>
          <button
            type="button"
            className={styles.iconButton}
            onClick={() => setMuted((value) => !value)}
            aria-label={muted ? "Unmute" : "Mute"}
            aria-pressed={muted}
          >
            {muted ? "🔇" : "🔊"}
          </button>
          <span className={styles.spacer} />
          <span className={styles.time}>
            {formatDuration(current)} / {formatDuration(duration)}
          </span>
        </div>
      </div>
    </section>
  );
}
