import { Route, Routes } from "react-router-dom";
import { ComingSoon } from "../pages/ComingSoon";
import { HomePage } from "../pages/HomePage";
import { LibraryPage } from "../pages/LibraryPage";
import { RecentPage } from "../pages/RecentPage";
import { TopicPage } from "../pages/TopicPage";
import { AppShell } from "./AppShell";

export function App() {
  return (
    <AppShell>
      <Routes>
        <Route path="/" element={<HomePage />} />
        <Route
          path="/explore"
          element={
            <ComingSoon
              title="Explore"
              description="Filter your library by topic, creator, and popularity. Arriving with the Explore filters work."
            />
          }
        />
        <Route
          path="/search"
          element={
            <ComingSoon
              title="Search"
              description="Full-text and semantic search across captions, transcripts, and creators."
            />
          }
        />
        <Route path="/library" element={<LibraryPage />} />
        <Route path="/library/recent" element={<RecentPage />} />
        <Route path="/topics/:slug" element={<TopicPage />} />
        <Route
          path="/downloads"
          element={
            <ComingSoon
              title="Downloads"
              description="Queue new clips and watch enrichment progress once the worker lands."
            />
          }
        />
        <Route
          path="/settings"
          element={
            <ComingSoon
              title="Settings"
              description="Capabilities, playback preferences, and diagnostics live here."
            />
          }
        />
      </Routes>
    </AppShell>
  );
}
