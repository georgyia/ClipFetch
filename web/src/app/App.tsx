import { Route, Routes } from "react-router-dom";
import { useBootstrap } from "../api/queries";
import { PrimaryNav } from "./PrimaryNav";

function Placeholder({ title }: { title: string }) {
  return <h1>{title}</h1>;
}

function Home() {
  const { data, isLoading, isError } = useBootstrap();

  if (isLoading) {
    return <p role="status">Loading your library…</p>;
  }
  if (isError || !data) {
    return <p role="alert">Could not reach the ClipFetch Watch server.</p>;
  }

  const count = data.libraries.length;
  return (
    <section aria-label="Library status">
      <h1>Home</h1>
      <p>
        ClipFetch Watch v{data.app_version} · {count} librar{count === 1 ? "y" : "ies"} registered
      </p>
    </section>
  );
}

export function App() {
  return (
    <div className="app-shell">
      <a className="skip-link" href="#main">
        Skip to content
      </a>
      <PrimaryNav />
      <main id="main">
        <Routes>
          <Route path="/" element={<Home />} />
          <Route path="/explore" element={<Placeholder title="Explore" />} />
          <Route path="/search" element={<Placeholder title="Search" />} />
          <Route path="/library" element={<Placeholder title="Library" />} />
          <Route path="/downloads" element={<Placeholder title="Downloads" />} />
          <Route path="/settings" element={<Placeholder title="Settings" />} />
        </Routes>
      </main>
    </div>
  );
}
