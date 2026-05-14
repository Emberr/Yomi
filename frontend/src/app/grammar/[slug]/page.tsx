"use client";

import Link from "next/link";
import { useCallback, useEffect, useState } from "react";
import { useParams, useRouter } from "next/navigation";
import { useAuth } from "@/contexts/auth-context";
import {
  apiCreateSrsCard,
  apiGetGrammar,
  apiGetGrammarSentences,
  type ExampleSentence,
  type GrammarDetail,
} from "@/lib/api";
import { Furigana } from "@/components/furigana";
import { JlptBadge } from "@/components/jlpt-badge";
import { TtsButton } from "@/components/tts-button";

export default function GrammarDetailPage() {
  const { auth } = useAuth();
  const router = useRouter();
  const params = useParams<{ slug: string }>();
  const slug = params.slug;

  const [grammar, setGrammar] = useState<GrammarDetail | null>(null);
  const [sentences, setSentences] = useState<ExampleSentence[]>([]);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);
  const [practiceState, setPracticeState] = useState<
    "idle" | "pending" | "done" | "error"
  >("idle");
  const [practiceError, setPracticeError] = useState<string | null>(null);

  useEffect(() => {
    if (auth.status === "unauthenticated") {
      router.replace("/login");
    }
  }, [auth.status, router]);

  const load = useCallback(async () => {
    if (!slug) return;
    setLoading(true);
    setError(null);
    try {
      const [gRes, sRes] = await Promise.all([
        apiGetGrammar(slug),
        apiGetGrammarSentences(slug),
      ]);
      if (!gRes.ok) {
        setError(gRes.error);
      } else {
        setGrammar(gRes.data);
        setSentences(sRes.ok ? sRes.data : []);
      }
    } catch {
      setError("Failed to load. Check your connection and try again.");
    } finally {
      setLoading(false);
    }
  }, [slug]);

  useEffect(() => {
    if (auth.status === "authenticated") {
      void load();
    }
  }, [auth.status, load]);

  async function handlePractice() {
    if (!grammar || practiceState === "pending") return;
    setPracticeState("pending");
    setPracticeError(null);
    const res = await apiCreateSrsCard({
      content_id: grammar.id,
      content_table: "grammar_points",
      card_type: "grammar_production",
    });
    if (res.ok) {
      setPracticeState("done");
    } else {
      setPracticeState("error");
      setPracticeError(res.error);
    }
  }

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

  if (loading) {
    return (
      <>
        <header className="topbar">
          <h1 className="page-title">Grammar</h1>
        </header>
        <div className="content-loading">Loading grammar point…</div>
      </>
    );
  }

  if (error || !grammar) {
    return (
      <>
        <header className="topbar">
          <h1 className="page-title">Grammar</h1>
        </header>
        <div className="content-error">
          {error ?? "Grammar point not found."}
          <Link className="back-link" href="/grammar">
            ← Back to grammar list
          </Link>
        </div>
      </>
    );
  }

  return (
    <>
      <header className="topbar">
        <div className="topbar-left">
          <Link className="back-link" href="/grammar">
            ← Grammar
          </Link>
          <h1 className="page-title" lang="ja">
            {grammar.title}
          </h1>
        </div>
        <JlptBadge level={grammar.jlpt_level} />
      </header>

      <div className="grammar-detail">
        {grammar.short_desc && (
          <section className="detail-section">
            <p className="grammar-short-desc">{grammar.short_desc}</p>
          </section>
        )}

        {grammar.long_desc && (
          <section className="detail-section">
            <h2 className="detail-heading">Explanation</h2>
            <p className="detail-body">{grammar.long_desc}</p>
          </section>
        )}

        {grammar.formation_pattern && (
          <section className="detail-section">
            <h2 className="detail-heading">Formation</h2>
            <p className="formation-pattern" lang="ja">
              {grammar.formation_pattern}
            </p>
          </section>
        )}

        {grammar.common_mistakes && (
          <section className="detail-section">
            <h2 className="detail-heading">Common Mistakes</h2>
            <p className="detail-body">{grammar.common_mistakes}</p>
          </section>
        )}

        {sentences.length > 0 && (
          <section className="detail-section">
            <h2 className="detail-heading">Examples</h2>
            <ul className="sentence-list">
              {sentences.map((s) => (
                <li className="sentence-item" key={s.id}>
                  <div className="sentence-japanese">
                    <Furigana
                      className="sentence-text"
                      japanese={s.japanese}
                      reading={s.reading || undefined}
                    />
                    <TtsButton text={s.japanese} />
                  </div>
                  {s.translation && (
                    <p className="sentence-translation">{s.translation}</p>
                  )}
                </li>
              ))}
            </ul>
          </section>
        )}

        {grammar.tags.length > 0 && (
          <section className="detail-section">
            <div className="tag-list">
              {grammar.tags.map((tag) => (
                <span className="tag" key={tag}>
                  {tag}
                </span>
              ))}
            </div>
          </section>
        )}

        <section className="detail-section detail-actions">
          {practiceState === "done" ? (
            <span className="practice-done">✓ Added to review queue</span>
          ) : (
            <button
              className="btn btn-primary practice-btn"
              disabled={practiceState === "pending"}
              onClick={() => void handlePractice()}
              type="button"
            >
              {practiceState === "pending" ? "Adding…" : "Practice this"}
            </button>
          )}
          {practiceState === "error" && practiceError && (
            <div className="form-error">{practiceError}</div>
          )}
        </section>
      </div>
    </>
  );
}
