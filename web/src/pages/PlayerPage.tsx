import { useCallback, useEffect, useRef, useState } from "react";
import { useNavigate, useParams, useSearchParams } from "react-router-dom";
import { useClipDetail, useClipList, usePlayback, useSavePlayback } from "../api/queries";
import { mediaUrl, posterUrl } from "../api/types";
import { Icon } from "../components/Icon";
import { Icons } from "../components/icons";
import { formatDuration } from "../lib/format";
import { parseQueueSource, seededShuffle } from "../lib/queueSource";
import { useReducedMotion } from "../lib/useReducedMotion";
import styles from "./PlayerPage.module.css";

// Persist progress at most this often while playing; also flushed on pause, end, and unmount.
const SAVE_INTERVAL_MS = 5000;
// Idle time before the control bar fades out during playback.
const CONTROLS_IDLE_MS = 2600;

/**
 * The immersive vertical player. Streams media by clip id (the backend serves byte ranges) with
 * auto-hiding glass controls, a scrubber that shows buffered range and a hover time preview, an
 * ambient glow behind the portrait video, and a queue sheet.
 *
 * This is the browser counterpart to the shipping terminal player in clipfetch/watcher.py: both
 * resolve a clip and play its local media, but the terminal player hands off to the OS player while
 * this one plays inline.
 */
export function PlayerPage() {
  const { id = "" } = useParams();
  const navigate = useNavigate();
  const [searchParams, setSearchParams] = useSearchParams();
  const [queueOpen, setQueueOpen] = useState(false);
  const videoRef = useRef<HTMLVideoElement>(null);
  const stageRef = useRef<HTMLElement>(null);
  const controlsRef = useRef<HTMLDivElement>(null);
  const reducedMotion = useReducedMotion();

  const { data: clip } = useClipDetail(id);
  const playback = usePlayback(id);
  const save = useSavePlayback();
  // The queue follows the context the player was opened with (topic/collection/Explore/search),
  // falling back to global-recent — so "watch many in this category" stays in that category.
  const source = parseQueueSource(searchParams);
  const queue = useClipList(source.key, source.buildPath);

  const available = (queue.data?.pages.flatMap((page) => page.items) ?? []).filter(
    (item) => item.available,
  );
  // Shuffle mode reorders the queue with a URL-carried seed so prev/next stays stable across hops.
  const shuffleOn = searchParams.get("shuffle") === "1";
  const order = shuffleOn ? seededShuffle(available, Number(searchParams.get("seed"))) : available;
  const index = order.findIndex((item) => item.id === id);
  const prevId = index > 0 ? order[index - 1].id : null;
  const nextId = index >= 0 && index < order.length - 1 ? order[index + 1].id : null;
  const upcoming = index >= 0 ? order.slice(index + 1) : [];

  const [playing, setPlaying] = useState(true);
  const [muted, setMuted] = useState(false);
  const [current, setCurrent] = useState(0);
  const [duration, setDuration] = useState(0);
  const [buffered, setBuffered] = useState(0);
  const [failed, setFailed] = useState(false);
  const [fullscreen, setFullscreen] = useState(false);
  const [controlsVisible, setControlsVisible] = useState(true);
  const [hoverTime, setHoverTime] = useState<{ time: number; x: number } | null>(null);

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
        // Carry the queue context across prev/next so the category isn't lost after one hop.
        const qs = searchParams.toString();
        navigate(`/watch/${encodeURIComponent(clipId)}${qs ? `?${qs}` : ""}`);
      }
    },
    [navigate, searchParams],
  );

  // Toggle shuffle in place, minting a fresh seed so the reshuffle is stable for the session.
  const toggleShuffle = useCallback(() => {
    const next = new URLSearchParams(searchParams);
    if (next.get("shuffle") === "1") {
      next.delete("shuffle");
      next.delete("seed");
    } else {
      next.set("shuffle", "1");
      next.set("seed", String(Math.floor(Math.random() * 1_000_000_000)));
    }
    setSearchParams(next, { replace: true });
  }, [searchParams, setSearchParams]);

  const toggleFullscreen = useCallback(() => {
    const stage = stageRef.current;
    if (!stage || typeof document === "undefined") {
      return;
    }
    if (document.fullscreenElement) {
      void document.exitFullscreen?.();
    } else {
      void stage.requestFullscreen?.();
    }
  }, []);

  useEffect(() => {
    const onChange = () => setFullscreen(Boolean(document.fullscreenElement));
    document.addEventListener("fullscreenchange", onChange);
    return () => document.removeEventListener("fullscreenchange", onChange);
  }, []);

  /*
   * Auto-hiding controls.
   *
   * The bar fades out after a period of inactivity, but only while the video is actually playing.
   * It never hides when paused (the user is looking at a still and needs the controls), when focus
   * is inside the control bar (a keyboard user would lose sight of where they are), or under
   * reduced motion. `reveal` is called from pointer, key, and touch activity.
   */
  const reveal = useCallback(() => {
    setControlsVisible(true);
  }, []);

  useEffect(() => {
    if (!playing || reducedMotion || queueOpen) {
      setControlsVisible(true);
      return;
    }
    if (!controlsVisible) {
      return;
    }
    const timer = window.setTimeout(() => {
      // Focus inside the controls means someone is using them; keep them on screen.
      if (controlsRef.current?.contains(document.activeElement)) {
        return;
      }
      setControlsVisible(false);
    }, CONTROLS_IDLE_MS);
    return () => window.clearTimeout(timer);
  }, [playing, reducedMotion, queueOpen, controlsVisible]);

  // Keyboard map. Ignored while a form control has focus.
  useEffect(() => {
    function onKey(event: KeyboardEvent) {
      const target = event.target as HTMLElement | null;
      if (target && /^(INPUT|TEXTAREA|SELECT)$/.test(target.tagName)) {
        return;
      }
      // Any key press counts as activity, so controls come back for keyboard-only use.
      reveal();
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
        case "s":
          toggleShuffle();
          break;
        case "q":
          setQueueOpen((value) => !value);
          break;
        case "f":
          toggleFullscreen();
          break;
        case "Escape":
          if (!document.fullscreenElement) {
            navigate(-1);
          }
          break;
        default:
          break;
      }
    }
    window.addEventListener("keydown", onKey);
    return () => window.removeEventListener("keydown", onKey);
  }, [togglePlay, seekBy, goTo, nextId, prevId, navigate, toggleShuffle, toggleFullscreen, reveal]);

  // Reset transient state and per-clip progress bookkeeping when the clip changes.
  // biome-ignore lint/correctness/useExhaustiveDependencies: id is the intended reset trigger
  useEffect(() => {
    setPlaying(true);
    setFailed(false);
    setCurrent(0);
    setBuffered(0);
    setControlsVisible(true);
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
  const progressPercent = duration > 0 ? (current / duration) * 100 : 0;
  const bufferedPercent = duration > 0 ? Math.min(100, (buffered / duration) * 100) : 0;
  const remaining = duration > 0 ? Math.max(0, duration - current) : 0;

  /** Map a pointer x within the scrubber track to a time, for the hover preview. */
  function previewAt(event: React.PointerEvent<HTMLDivElement>) {
    if (duration <= 0) {
      return;
    }
    const box = event.currentTarget.getBoundingClientRect();
    const ratio = Math.max(0, Math.min(1, (event.clientX - box.left) / box.width));
    setHoverTime({ time: ratio * duration, x: ratio * box.width });
  }

  return (
    <section
      ref={stageRef}
      className={styles.stage}
      aria-label="Player"
      data-controls={controlsVisible ? "visible" : "hidden"}
      onPointerMove={reveal}
      onPointerDown={reveal}
    >
      {/*
        Ambient glow: the clip's own poster, scaled and heavily blurred behind the video, so a 9:16
        clip fills a 16:9 screen with its own colour instead of black bars. Derived from the poster
        rather than sampled per frame — sampling means a canvas readback every frame, which costs
        more than the effect is worth. Purely decorative.
      */}
      {clip && !reducedMotion ? (
        <img className={styles.ambient} src={posterUrl(id)} alt="" aria-hidden="true" />
      ) : null}

      <div className={styles.topBar} data-visible={controlsVisible}>
        <button
          type="button"
          className={styles.close}
          onClick={() => navigate(-1)}
          aria-label="Close player"
        >
          <Icon icon={Icons.close} size="md" />
        </button>
        <h1 className={styles.heading}>{title}</h1>
        {index >= 0 && order.length > 0 ? (
          <span className={styles.position}>
            {index + 1} / {order.length}
          </span>
        ) : null}
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
          onProgress={(event) => {
            // The buffered range that covers the playhead — what a scrubber should actually show.
            const video = event.currentTarget;
            const ranges = video.buffered;
            for (let i = 0; i < ranges.length; i++) {
              if (ranges.start(i) <= video.currentTime && ranges.end(i) >= video.currentTime) {
                setBuffered(ranges.end(i));
                return;
              }
            }
          }}
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

      <div className={styles.controls} ref={controlsRef} data-visible={controlsVisible}>
        {/*
          The scrubber layers a buffered bar and a played bar under a native range input. Keeping
          the real input means keyboard seeking, ARIA, and touch behaviour come for free; the
          visible bars are painted underneath it.
        */}
        <div
          className={styles.scrubber}
          onPointerMove={previewAt}
          onPointerLeave={() => setHoverTime(null)}
        >
          <div className={styles.track} aria-hidden="true">
            <div className={styles.buffered} style={{ width: `${bufferedPercent}%` }} />
            <div className={styles.played} style={{ width: `${progressPercent}%` }} />
          </div>
          <input
            className={styles.range}
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
            aria-valuetext={`${formatDuration(current)} of ${formatDuration(duration)}`}
          />
          {hoverTime ? (
            <span
              className={styles.hoverBubble}
              style={{ left: `${hoverTime.x}px` }}
              aria-hidden="true"
            >
              {formatDuration(hoverTime.time)}
            </span>
          ) : null}
        </div>

        <div className={styles.buttons}>
          <span className={styles.time}>{formatDuration(current)}</span>
          <button
            type="button"
            className={styles.iconButton}
            onClick={() => goTo(prevId)}
            disabled={!prevId}
            aria-label="Previous clip"
          >
            <Icon icon={Icons.previous} size="md" />
          </button>
          <button
            type="button"
            className={`${styles.iconButton} ${styles.playButton}`}
            onClick={togglePlay}
            aria-label={playing ? "Pause" : "Play"}
          >
            <Icon icon={playing ? Icons.pause : Icons.play} size="lg" />
          </button>
          <button
            type="button"
            className={styles.iconButton}
            onClick={() => goTo(nextId)}
            disabled={!nextId}
            aria-label="Next clip"
          >
            <Icon icon={Icons.next} size="md" />
          </button>
          <button
            type="button"
            className={styles.iconButton}
            onClick={() => setMuted((value) => !value)}
            aria-label={muted ? "Unmute" : "Mute"}
            aria-pressed={muted}
          >
            <Icon icon={muted ? Icons.mute : Icons.unmute} size="md" />
          </button>
          <button
            type="button"
            className={`${styles.iconButton} ${shuffleOn ? styles.active : ""}`.trim()}
            onClick={toggleShuffle}
            aria-label="Shuffle"
            aria-pressed={shuffleOn}
          >
            <Icon icon={Icons.shuffle} size="md" />
          </button>
          <button
            type="button"
            className={`${styles.iconButton} ${queueOpen ? styles.active : ""}`.trim()}
            onClick={() => setQueueOpen((value) => !value)}
            aria-label="Up next"
            aria-expanded={queueOpen}
          >
            <Icon icon={Icons.queue} size="md" />
          </button>
          <button
            type="button"
            className={styles.iconButton}
            onClick={toggleFullscreen}
            aria-label={fullscreen ? "Exit full screen" : "Full screen"}
            aria-pressed={fullscreen}
          >
            <Icon icon={fullscreen ? Icons.exitFullscreen : Icons.fullscreen} size="md" />
          </button>
          <span className={styles.spacer} />
          <span className={styles.time}>−{formatDuration(remaining)}</span>
        </div>
      </div>

      {queueOpen ? (
        <aside className={styles.queue} aria-label="Up next" data-testid="up-next">
          <div className={styles.queueHeader}>
            <h2 className={styles.queueTitle}>Up next{shuffleOn ? " · shuffled" : ""}</h2>
            <button
              type="button"
              className={styles.queueClose}
              onClick={() => setQueueOpen(false)}
              aria-label="Close up next"
            >
              <Icon icon={Icons.close} size="sm" />
            </button>
          </div>
          {upcoming.length === 0 ? (
            <p className={styles.queueEmpty}>You're at the end of the queue.</p>
          ) : (
            <ol className={styles.queueList}>
              {upcoming.map((item, position) => (
                <li key={item.id}>
                  <button
                    type="button"
                    className={styles.queueItem}
                    onClick={() => {
                      setQueueOpen(false);
                      goTo(item.id);
                    }}
                  >
                    <img
                      className={styles.queueThumb}
                      src={posterUrl(item.id)}
                      alt=""
                      loading="lazy"
                      decoding="async"
                    />
                    <span className={styles.queueMeta}>
                      <span className={styles.queueLabel}>
                        {item.caption?.trim() || item.author || item.id}
                      </span>
                      {item.author ? (
                        <span className={styles.queueAuthor}>@{item.author}</span>
                      ) : null}
                    </span>
                    <span className={styles.queuePosition} aria-hidden="true">
                      {position + 1}
                    </span>
                  </button>
                </li>
              ))}
            </ol>
          )}
        </aside>
      ) : null}

      {/* Warm the next clip's media so advancing is gapless. */}
      {nextId ? (
        <video
          className={styles.prefetch}
          src={mediaUrl(nextId)}
          preload="auto"
          muted
          aria-hidden="true"
          tabIndex={-1}
          data-testid="prefetch-next"
        />
      ) : null}
    </section>
  );
}
