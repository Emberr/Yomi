"use client";

import Link from "next/link";
import { Suspense, useCallback, useEffect, useState } from "react";
import { useRouter, useSearchParams } from "next/navigation";
import { useAuth } from "@/contexts/auth-context";
import { apiListGrammar, type GrammarSummary } from "@/lib/api";
import { JlptBadge } from "@/components/jlpt-badge";

const LEVELS = ["All", "N5", "N4", "N3", "N2", "N1"] as const;
type Level = (typeof LEVELS)[number];

function isValidLevel(s: string | null): s is Exclude<Level, "All"> {
  return s !== null && (LEVELS as readonly string[]).includes(s) && s !== "All";
}

// ── Inner component (reads searchParams, safe inside Suspense) ────────────────

function GrammarPageInner() {
  const { auth } = useAuth();
  const router = useRouter();
  const searchParams = useSearchParams();

  const initialLevel: Level = isValidLevel(searchParams.get("level"))
    ? (searchParams.get("level") as Exclude<Level, "All">)
    : "All";

  const [level, setLevel] = useState<Level>(initialLevel);
  const [items, setItems] = useState<GrammarSummary[]>([]);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);

  useEffect(() => {
    if (auth.status === "unauthenticated") {
      router.replace("/login");
    }
  }, [auth.status, router]);

  const load = useCallback(async (selectedLevel: Level) => {
    setLoading(true);
    setError(null);
    const res = await apiListGrammar(
      selectedLevel === "All" ? undefined : selectedLevel,
    );
    if (res.ok) {
      setItems(res.data);
    } else {
      setError(res.error);
    }
    setLoading(false);
  }, []);

  useEffect(() => {
    if (auth.status === "authenticated") {
      void load(level);
    }
  }, [auth.status, level, load]);

  if (auth.status === "loading") {
    return (
      <>
        <header className="topbar">
          <h1 className="page-title">Grammar</h1>
        </header>
        <div className="content-loading">Loading…</div>
      </>
    );
  }

  if (auth.status === "unauthenticated") return null;

  return (
    <>
      <header className="topbar">
        <h1 className="page-title">Grammar</h1>
      </header>

      <div className="level-tabs" role="tablist" aria-label="JLPT level filter">
        {LEVELS.map((l) => (
          <button
            aria-pressed={level === l}
            className={`level-tab${level === l ? " level-tab-active" : ""}`}
            key={l}
            onClick={() => setLevel(l)}
            role="tab"
            type="button"
          >
            {l}
          </button>
        ))}
      </div>

      {error && <div className="form-error">{error}</div>}

      {loading ? (
        <div className="content-loading">Loading grammar points…</div>
      ) : items.length === 0 ? (
        <div className="content-empty">
          No grammar points found
          {level !== "All" ? ` for ${level}` : ""}.
        </div>
      ) : (
        <ul className="grammar-list" aria-label="Grammar points">
          {items.map((item) => (
            <li key={item.id}>
              <Link
                className="grammar-item"
                href={
                  level !== "All"
                    ? `/grammar/${item.slug}?from=${level}`
                    : `/grammar/${item.slug}`
                }
              >
                <div className="grammar-item-head">
                  <span className="grammar-item-title" lang="ja">
                    {item.title}
                  </span>
                  <JlptBadge level={item.jlpt_level} />
                </div>
                {item.short_desc && (
                  <p className="grammar-item-desc">{item.short_desc}</p>
                )}
              </Link>
            </li>
          ))}
        </ul>
      )}
    </>
  );
}

// ── Page export ───────────────────────────────────────────────────────────────

export default function GrammarPage() {
  return (
    <Suspense
      fallback={
        <>
          <header className="topbar">
            <h1 className="page-title">Grammar</h1>
          </header>
          <div className="content-loading">Loading…</div>
        </>
      }
    >
      <GrammarPageInner />
    </Suspense>
  );
}
