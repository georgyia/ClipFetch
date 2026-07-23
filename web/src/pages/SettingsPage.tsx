import { useState } from "react";
import { useAccounts, useConnectAccount, useDiagnostics } from "../api/queries";
import { Button } from "../components/Button";
import { ErrorState } from "../components/ErrorState";
import { LoadingState } from "../components/LoadingState";
import { titleize } from "../lib/format";
import styles from "./SettingsPage.module.css";

// Settings surface: capabilities, worker/schema state, and a redacted support bundle the user can
// copy into a bug report. The bundle contains only versions, counts, and flags — no paths or names.
export function SettingsPage() {
  const { data, isLoading, isError } = useDiagnostics();
  const accounts = useAccounts();
  const connect = useConnectAccount();
  const [copied, setCopied] = useState(false);

  async function copyBundle() {
    if (!data) {
      return;
    }
    try {
      await navigator.clipboard.writeText(JSON.stringify(data, null, 2));
      setCopied(true);
      setTimeout(() => setCopied(false), 2000);
    } catch {
      setCopied(false);
    }
  }

  if (isLoading) {
    return <LoadingState label="Loading diagnostics…" />;
  }
  if (isError || !data) {
    return <ErrorState title="Could not load diagnostics" description="Try again in a moment." />;
  }

  const capabilities = Object.entries(data.capabilities);
  return (
    <section aria-label="Settings">
      <div className={styles.header}>
        <h1>Settings</h1>
        <Button onClick={copyBundle}>Copy support bundle</Button>
      </div>
      {copied ? (
        <p className={styles.copied} role="status">
          Support bundle copied to clipboard.
        </p>
      ) : null}

      <div className={styles.grid}>
        <div className={styles.card}>
          <h2 className={styles.cardTitle}>App</h2>
          <dl className={styles.rows}>
            <dt>Version</dt>
            <dd>{data.app_version}</dd>
            <dt>Worker</dt>
            <dd>{data.worker.state}</dd>
            <dt>App-state schema</dt>
            <dd>{data.schema.appstate}</dd>
            <dt>Catalog schema</dt>
            <dd>{data.schema.catalog ?? "—"}</dd>
          </dl>
        </div>

        <div className={styles.card}>
          <h2 className={styles.cardTitle}>Library</h2>
          <dl className={styles.rows}>
            <dt>Registered</dt>
            <dd>{data.libraries.count}</dd>
            <dt>Active health</dt>
            <dd>{data.libraries.active?.health ?? "—"}</dd>
            <dt>Active clips</dt>
            <dd>{data.libraries.active?.clip_count ?? "—"}</dd>
          </dl>
        </div>

        <div className={styles.card}>
          <h2 className={styles.cardTitle}>Capabilities</h2>
          <dl className={styles.rows}>
            {capabilities.map(([name, capability]) => (
              <div key={name} style={{ display: "contents" }}>
                <dt>{titleize(name)}</dt>
                <dd className={capability.available ? styles.available : styles.unavailable}>
                  {capability.available ? "Available" : "Off"}
                </dd>
              </div>
            ))}
          </dl>
        </div>

        <div className={styles.card}>
          <h2 className={styles.cardTitle}>Accounts</h2>
          <dl className={styles.rows}>
            {(accounts.data?.accounts ?? []).map((account) => (
              <div key={account.platform} style={{ display: "contents" }}>
                <dt>{account.label}</dt>
                <dd className={account.connected ? styles.available : styles.unavailable}>
                  {account.connected ? "Connected" : account.state}
                  {!account.connected && account.state !== "no_display" ? (
                    <>
                      {" "}
                      <Button
                        variant="ghost"
                        onClick={() => connect.mutate(account.platform)}
                        disabled={connect.isPending || account.state === "connecting"}
                      >
                        Connect
                      </Button>
                    </>
                  ) : null}
                </dd>
              </div>
            ))}
          </dl>
        </div>

        <div className={styles.card}>
          <h2 className={styles.cardTitle}>Platforms</h2>
          <dl className={styles.rows}>
            {data.platforms.map((platform) => (
              <div key={platform.name} style={{ display: "contents" }}>
                <dt>{platform.name}</dt>
                <dd>{platform.support}</dd>
              </div>
            ))}
          </dl>
        </div>

        <div className={styles.card}>
          <h2 className={styles.cardTitle}>Jobs</h2>
          <dl className={styles.rows}>
            {Object.entries(data.jobs).map(([state, count]) => (
              <div key={state} style={{ display: "contents" }}>
                <dt>{titleize(state)}</dt>
                <dd>{count}</dd>
              </div>
            ))}
          </dl>
        </div>
      </div>
    </section>
  );
}
