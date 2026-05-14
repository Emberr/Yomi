"use client";

import { useEffect, useRef, useState } from "react";
import { useRouter } from "next/navigation";
import { useAuth } from "@/contexts/auth-context";
import {
  apiCreateSrsCard,
  apiGetVocab,
  apiSearchVocab,
  type VocabDetail,
  type VocabSummary,
} from "@/lib/api";
import { JlptBadge } from "@/components/jlpt-badge";

const DEBOUNCE_MS = 300;

type PracticeState = "idle" | "pending" | "done" | "error";

interface VocabItemRowProps {
  item: VocabSummary;
}

function VocabItemRow({ item }: VocabItemRowProps) {
  const [expanded, setExpanded] = useState(false);
  const [detail, setDetail] = useState<VocabDetail | null>(null);
  const [detailError, setDetailError] = useState<string | null>(null);
  const [practiceState, setPracticeState] = useState<PracticeState>("idle");
  const [practiceError, setPracticeError] = useState<string | null>(null);

  async function toggleDetail() {
    if (expanded) {
      setExpanded(false);
      return;
    }
    if (!detail) {
      const res = await apiGetVocab(item.id);
      if (res.ok) {
        setDetail(res.data);
      } else {
        setDetailError(res.error);
      }
    }
    setExpanded(true);
  }

  async function handlePractice() {
    if (practiceState === "pending") return;
    setPracticeState("pending");
    setPracticeError(null);
    const res = await apiCreateSrsCard({
      content_id: item.id,
      content_table: "vocab_items",
      card_type: "vocab_meaning",
    });
    if (res.ok) {
      setPracticeState("done");
    } else {
      setPracticeState("error");
      setPracticeError(res.error);
    }
  }

  const display =
    item.kanji_forms.length > 0 ? item.kanji_forms[0] : item.reading_forms[0];
  const reading = item.kanji_forms.length > 0 ? item.reading_forms[0] : null;
  const meanings = item.meanings.slice(0, 3).join("; ");

  return (
    <li className="vocab-item">
      <button
        aria-expanded={expanded}
        className="vocab-item-main"
        onClick={() => void toggleDetail()}
        type="button"
      >
        <div className="vocab-item-head">
          <span className="vocab-kanji" lang="ja">
            {display}
          </span>
          {reading && (
            <span className="vocab-reading" lang="ja">
              {reading}
            </span>
          )}
          {item.jlpt_level && <JlptBadge level={item.jlpt_level} />}
        </div>
        <p className="vocab-meanings">{meanings}</p>
      </button>

      {expanded && (
        <div className="vocab-detail">
          {detailError && (
            <p className="form-error">{detailError}</p>
          )}
          {detail && (
            <>
              <div className="vocab-detail-forms">
                {detail.kanji_forms.length > 1 && (
                  <div className="vocab-forms-row">
                    <span className="vocab-forms-label">Kanji:</span>
                    <span lang="ja">{detail.kanji_forms.join("、")}</span>
                  </div>
                )}
                {detail.reading_forms.length > 0 && (
                  <div className="vocab-forms-row">
                    <span className="vocab-forms-label">Readings:</span>
                    <span lang="ja">{detail.reading_forms.join("、")}</span>
                  </div>
                )}
                {detail.pos_tags.length > 0 && (
                  <div className="vocab-forms-row">
                    <span className="vocab-forms-label">Type:</span>
                    <span>{detail.pos_tags.join(", ")}</span>
                  </div>
                )}
                {detail.frequency !== null && (
                  <div className="vocab-forms-row">
                    <span className="vocab-forms-label">Frequency:</span>
                    <span>{detail.frequency}</span>
                  </div>
                )}
              </div>
              <ul className="vocab-meanings-full">
                {detail.meanings.map((m, i) => (
                  <li key={i}>{m}</li>
                ))}
              </ul>
            </>
          )}
          <div className="vocab-actions">
            {practiceState === "done" ? (
              <span className="practice-done">✓ Added to review queue</span>
            ) : (
              <button
                className="btn btn-ghost btn-sm"
                disabled={practiceState === "pending"}
                onClick={() => void handlePractice()}
                type="button"
              >
                {practiceState === "pending" ? "Adding…" : "Add to review queue"}
              </button>
            )}
            {practiceState === "error" && practiceError && (
              <span className="form-error">{practiceError}</span>
            )}
          </div>
        </div>
      )}
    </li>
  );
}

export default function VocabularyPage() {
  const { auth } = useAuth();
  const router = useRouter();

  const [query, setQuery] = useState("");
  const [results, setResults] = useState<VocabSummary[]>([]);
  const [searching, setSearching] = useState(false);
  const [searchError, setSearchError] = useState<string | null>(null);
  const [searched, setSearched] = useState(false);
  const debounceRef = useRef<ReturnType<typeof setTimeout> | null>(null);

  useEffect(() => {
    if (auth.status === "unauthenticated") {
      router.replace("/login");
    }
  }, [auth.status, router]);

  useEffect(() => {
    if (debounceRef.current) clearTimeout(debounceRef.current);
    const trimmed = query.trim();
    if (!trimmed || auth.status !== "authenticated") {
      setResults([]);
      setSearched(false);
      return;
    }
    debounceRef.current = setTimeout(() => {
      void (async () => {
        setSearching(true);
        setSearchError(null);
        const res = await apiSearchVocab(trimmed);
        if (res.ok) {
          setResults(res.data);
          setSearched(true);
        } else {
          setSearchError(res.error);
        }
        setSearching(false);
      })();
    }, DEBOUNCE_MS);

    return () => {
      if (debounceRef.current) clearTimeout(debounceRef.current);
    };
  }, [query, auth.status]);

  if (auth.status === "loading") {
    return (
      <>
        <header className="topbar">
          <h1 className="page-title">Vocabulary</h1>
        </header>
        <div className="content-loading">Loading…</div>
      </>
    );
  }

  if (auth.status === "unauthenticated") return null;

  return (
    <>
      <header className="topbar">
        <h1 className="page-title">Vocabulary</h1>
      </header>

      <div className="vocab-search-bar">
        <input
          aria-label="Search vocabulary"
          autoComplete="off"
          className="form-input vocab-search-input"
          onChange={(e) => setQuery(e.target.value)}
          placeholder="Search: 食べる, eat, taberu…"
          spellCheck={false}
          type="search"
          value={query}
        />
        {searching && <span className="search-spinner" aria-live="polite">Searching…</span>}
      </div>

      {searchError && <div className="form-error">{searchError}</div>}

      {!query.trim() && (
        <p className="content-hint">
          Enter a word, reading, or meaning to search JMDict.
        </p>
      )}

      {searched && results.length === 0 && !searching && (
        <div className="content-empty">No results for &ldquo;{query}&rdquo;.</div>
      )}

      {results.length > 0 && (
        <ul className="vocab-list" aria-label="Vocabulary results">
          {results.map((item) => (
            <VocabItemRow item={item} key={item.id} />
          ))}
        </ul>
      )}
    </>
  );
}
