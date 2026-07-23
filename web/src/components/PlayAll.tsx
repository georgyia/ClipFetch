import { useNavigate } from "react-router-dom";
import type { ClipSummary } from "../api/types";
import { type QueueContext, watchLink } from "../lib/queueSource";
import { Button } from "./Button";
import styles from "./PlayAll.module.css";

// "Play all" / "Shuffle" entry points for a browsing surface: they open the player with this list as
// the queue (via the shared queue context), so the viewer can binge a whole category. Hidden when
// nothing is playable.
export function PlayAll({ items, context }: { items: ClipSummary[]; context: QueueContext }) {
  const navigate = useNavigate();
  const playable = items.filter((item) => item.available);
  if (playable.length === 0) {
    return null;
  }

  const playAll = () => navigate(watchLink(playable[0].id, context));
  const shuffle = () => {
    const start = playable[Math.floor(Math.random() * playable.length)].id;
    navigate(watchLink(start, context, { shuffle: true }));
  };

  return (
    <div className={styles.actions}>
      <Button onClick={playAll} aria-label="Play all clips in this view">
        ▶ Play all
      </Button>
      <Button onClick={shuffle} aria-label="Shuffle-play clips in this view">
        🔀 Shuffle
      </Button>
    </div>
  );
}
