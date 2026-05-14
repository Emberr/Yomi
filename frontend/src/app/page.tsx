"use client";

import { useEffect, useState, useCallback } from "react";
import { useRouter } from "next/navigation";
import Link from "next/link";
import { useAuth } from "@/contexts/auth-context";
import {
  apiGetProgressSummary,
  apiGetWeakPoints,
  type ProgressSummary,
  type WeakPoint,
} from "@/lib/api";

function StatCard({
  label,
  value,
  sub,
}: {
  label: string;
  value: string | number;
  sub?: string;
}) {
  return (
    <div className="stat-card">
      <span className="stat-value">{value}</span>
      <span className="stat-label">{label}</span>
      {sub && <span className="stat-sub">{sub}</span>}
    </div>
  );
}

function StateBreakdown({ counts }: { counts: ProgressSummary["cards_by_state"] }) {
  const entries = [
    { key: "new", label: "New" },
    { key: "learning", label: "Learning" },
    { key: "review", label: "Review" },
    { key: "relearning", label: "Relearning" },
  ] as const;
  const total = Object.values(counts).reduce((a, b) => a + b, 0);
  if (total === 0) return <p className="muted-note">No cards in deck yet.</p>;
  return (
    <div className="state-breakdown">
      {entries.map(({ key, label }) => (
        <span key={key} className={`state-badge state-badge-${key}`}>
          {label}: {counts[key]}
        </span>
      ))}
    </div>
  );
}

function WeakPointsList({ points }: { points: WeakPoint[] }) {
  if (points.length === 0)
    return <p className="muted-note">No weak points yet — keep reviewing!</p>;
  return (
    <ul className="weak-points-list">
      {points.slice(0, 5).map((p, i) => (
        <li key={i} className="weak-point-item">
          <span className="weak-point-name">
            {p.card_type} · {p.content_table}
          </span>
          <span className="weak-point-rate">
            {Math.round(p.correct_rate * 100)}% correct
            <span className="weak-point-count"> ({p.total_reviews} reviews)</span>
          </span>
        </li>
      ))}
    </ul>
  );
}

export default function Home() {
  const { auth } = useAuth();
  const router = useRouter();

  const [summary, setSummary] = useState<ProgressSummary | null>(null);
  const [weakPoints, setWeakPoints] = useState<WeakPoint[]>([]);
  const [loadError, setLoadError] = useState<string | null>(null);
  const [loading, setLoading] = useState(true);

  const load = useCallback(async () => {
    setLoading(true);
    setLoadError(null);
    try {
      const [sRes, wRes] = await Promise.all([
        apiGetProgressSummary(),
        apiGetWeakPoints(),
      ]);
      if (!sRes.ok) {
        setLoadError(sRes.error);
      } else {
        setSummary(sRes.data);
        setWeakPoints(wRes.ok ? wRes.data : []);
      }
    } catch {
      setLoadError("Failed to load progress data.");
    } finally {
      setLoading(false);
    }
  }, []);

  useEffect(() => {
    if (auth.status === "unauthenticated") {
      router.replace("/login");
      return;
    }
    if (auth.status === "authenticated") {
      void load();
    }
  }, [auth.status, router, load]);

  if (auth.status === "loading" || (auth.status === "authenticated" && loading)) {
    return (
      <>
        <header className="topbar">
          <h1 className="page-title">Dashboard</h1>
        </header>
        <section className="dashboard" aria-label="Loading">
          <div className="panel">
            <p>Loading…</p>
          </div>
        </section>
      </>
    );
  }

  if (auth.status === "unauthenticated") return null;

  return (
    <>
      <header className="topbar">
        <h1 className="page-title">Dashboard</h1>
      </header>
      <section className="dashboard" aria-label="Dashboard">
        {loadError && (
          <div className="panel panel-error" role="alert">
            {loadError}
          </div>
        )}

        <div className="panel">
          <h2 className="panel-heading">
            Welcome back, {auth.user.display_name}
          </h2>

          {summary && (
            <>
              <div className="stats-row">
                <StatCard label="Due Today" value={summary.due_today} />
                <StatCard label="Total Cards" value={summary.total_cards} />
                <StatCard label="Reviews Today" value={summary.reviews_today} />
                <StatCard
                  label="Streak"
                  value={`${summary.current_streak}d`}
                  sub={summary.current_streak === 0 ? "Start today!" : undefined}
                />
                <StatCard label="Total Reviews" value={summary.total_reviews} />
              </div>

              <div className="dashboard-section">
                <h3 className="section-heading">Cards by state</h3>
                <StateBreakdown counts={summary.cards_by_state} />
              </div>
            </>
          )}

          {!summary && !loadError && (
            <div className="stats-row">
              {[
                "Due Today",
                "Total Cards",
                "Reviews Today",
                "Streak",
                "Total Reviews",
              ].map((l) => (
                <StatCard key={l} label={l} value="—" />
              ))}
            </div>
          )}
        </div>

        <div className="panel">
          <h3 className="panel-heading">Quick actions</h3>
          <div className="dashboard-actions">
            <Link href="/review" className="btn btn-accent">
              {summary && summary.due_today > 0
                ? `Review (${summary.due_today} due)`
                : "Review"}
            </Link>
            <Link href="/grammar" className="btn btn-secondary">
              Browse Grammar
            </Link>
            <Link href="/vocabulary" className="btn btn-secondary">
              Browse Vocabulary
            </Link>
          </div>
        </div>

        <div className="panel">
          <h3 className="panel-heading">Weak points</h3>
          <WeakPointsList points={weakPoints} />
        </div>
      </section>
    </>
  );
}
