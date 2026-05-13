"use client";

import { useEffect, useState } from "react";

type HealthResponse = {
  status?: string;
  version?: string;
  databases?: {
    content?: {
      status?: string;
      schema_version?: string | null;
    };
    user?: {
      status?: string;
      schema_version?: string | null;
    };
  };
};

type HealthState =
  | { kind: "loading" }
  | { kind: "ok"; data: HealthResponse }
  | { kind: "error"; message: string };

const apiBase = process.env.NEXT_PUBLIC_API_BASE ?? "/api";

export function HealthPanel() {
  const [health, setHealth] = useState<HealthState>({ kind: "loading" });

  useEffect(() => {
    let cancelled = false;

    async function loadHealth() {
      try {
        const response = await fetch(`${apiBase}/health`, {
          headers: { Accept: "application/json" },
        });
        if (!response.ok) {
          throw new Error(`HTTP ${response.status}`);
        }
        const data = (await response.json()) as HealthResponse;
        if (!cancelled) {
          setHealth({ kind: "ok", data });
        }
      } catch (error) {
        if (!cancelled) {
          setHealth({
            kind: "error",
            message: error instanceof Error ? error.message : "Unavailable",
          });
        }
      }
    }

    void loadHealth();

    return () => {
      cancelled = true;
    };
  }, []);

  if (health.kind === "loading") {
    return (
      <div className="panel">
        <h2>API</h2>
        <p>Checking backend health.</p>
      </div>
    );
  }

  if (health.kind === "error") {
    return (
      <div className="panel">
        <h2>API</h2>
        <p>Backend health is unavailable from this frontend runtime.</p>
        <div className="health-grid">
          <HealthItem label="Status" value={health.message} />
          <HealthItem label="API base" value={apiBase} />
        </div>
      </div>
    );
  }

  const content = health.data.databases?.content;
  const user = health.data.databases?.user;

  return (
    <div className="panel">
      <h2>API</h2>
      <p>Backend health endpoint responded.</p>
      <div className="health-grid">
        <HealthItem label="Status" value={health.data.status ?? "unknown"} />
        <HealthItem label="Version" value={health.data.version ?? "unknown"} />
        <HealthItem
          label="content.db"
          value={`${content?.status ?? "unknown"} / ${
            content?.schema_version ?? "no schema"
          }`}
        />
        <HealthItem
          label="user.db"
          value={`${user?.status ?? "unknown"} / ${
            user?.schema_version ?? "no schema"
          }`}
        />
      </div>
    </div>
  );
}

function HealthItem({ label, value }: { label: string; value: string }) {
  return (
    <div className="health-item">
      <span className="health-label">{label}</span>
      <span className="health-value">{value}</span>
    </div>
  );
}

