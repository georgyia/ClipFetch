import { Chip } from "./Chip";
import { Icons } from "./icons";

export interface TopicChipProps {
  label: string;
  /** Clip count for this topic, when the caller has it. */
  count?: number | null;
  /** Makes the chip a link to the topic page. Static text otherwise. */
  linkToTopic?: boolean;
}

function titleize(slug: string): string {
  return slug
    .split("-")
    .map((part) => (part ? part[0].toUpperCase() + part.slice(1) : part))
    .join(" ");
}

export function TopicChip({ label, count, linkToTopic }: TopicChipProps) {
  return (
    <Chip
      icon={Icons.topics}
      count={count}
      to={linkToTopic ? `/topics/${encodeURIComponent(label)}` : undefined}
    >
      {titleize(label)}
    </Chip>
  );
}
