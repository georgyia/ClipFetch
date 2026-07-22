import { EmptyState } from "../components/EmptyState";

export interface ComingSoonProps {
  title: string;
  description: string;
}

// Shared placeholder for routes whose full experience arrives in a later backlog item. Keeps the
// app shell fully navigable without pretending the feature already works.
export function ComingSoon({ title, description }: ComingSoonProps) {
  return (
    <section aria-label={title}>
      <h1>{title}</h1>
      <EmptyState title="Coming soon" description={description} />
    </section>
  );
}
