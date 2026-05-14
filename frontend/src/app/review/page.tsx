"use client";

import { useEffect, useCallback, useState } from "react";
import { useRouter } from "next/navigation";
import { useAuth } from "@/contexts/auth-context";
import { apiGetDueCards, apiSubmitReview, type SrsCard } from "@/lib/api";
import { ReviewCard } from "@/components/review-card";
import { ReviewSessionSummary } from "@/components/review-session-summary";

type Distribution = Record<1 | 2 | 3 | 4, number>;

const EMPTY_DISTRIBUTION: Distribution = { 1: 0, 2: 0, 3: 0, 4: 0 };

export default function ReviewPage() {
  const { auth } = useAuth();
  const router = useRouter();

  const [cards, setCards] = useState<SrsCard[]>([]);
  const [index, setIndex] = useState(0);
  const [revealed, setRevealed] = useState(false);
  const [submitting, setSubmitting] = useState(false);
  const [cardError, setCardError] = useState<string | null>(null);
  const [done, setDone] = useState(false);
  const [distribution, setDistribution] = useState<Distribution>({ ...EMPTY_DISTRIBUTION });
  const [reviewed, setReviewed] = useState(0);
  const [startTime, setStartTime] = useState<number>(Date.now());
  const [loading, setLoading] = useState(true);
  const [fetchError, setFetchError] = useState<string | null>(null);

  // Auth guard
  useEffect(() => {
    if (auth.status === "unauthenticated") {
      router.push("/login");
    }
  }, [auth.status, router]);

  // Load due cards
  useEffect(() => {
    if (auth.status !== "authenticated") return;
    let cancelled = false;

    void (async () => {
      const result = await apiGetDueCards();
      if (cancelled) return;
      if (!result.ok) {
        setFetchError(result.error);
      } else {
        setCards(result.data);
        if (result.data.length === 0) setDone(true);
      }
      setLoading(false);
    })();

    return () => { cancelled = true; };
  }, [auth.status]);

  const handleReveal = useCallback(() => {
    setRevealed(true);
  }, []);

  const handleRate = useCallback(
    async (rating: 1 | 2 | 3 | 4) => {
      if (submitting) return;
      const card = cards[index];
      if (!card) return;

      setSubmitting(true);
      setCardError(null);

      const timeTakenMs = Date.now() - startTime;
      const result = await apiSubmitReview({
        card_id: card.id,
        rating,
        time_taken_ms: timeTakenMs,
      });

      if (!result.ok) {
        setCardError(result.error);
        setSubmitting(false);
        return;
      }

      const newDist = { ...distribution, [rating]: distribution[rating] + 1 };
      setDistribution(newDist);
      setReviewed((r) => r + 1);

      const nextIndex = index + 1;
      if (nextIndex >= cards.length) {
        setDone(true);
      } else {
        setIndex(nextIndex);
        setRevealed(false);
        setStartTime(Date.now());
      }
      setSubmitting(false);
    },
    [submitting, cards, index, startTime, distribution],
  );

  // Keyboard shortcuts
  useEffect(() => {
    function onKey(e: KeyboardEvent) {
      if (e.target instanceof HTMLInputElement || e.target instanceof HTMLTextAreaElement) return;
      if (loading || done || fetchError) return;

      switch (e.key) {
        case " ":
          e.preventDefault();
          if (!revealed && !submitting) handleReveal();
          break;
        case "1":
          if (revealed && !submitting) void handleRate(1);
          break;
        case "2":
          if (revealed && !submitting) void handleRate(2);
          break;
        case "3":
          if (revealed && !submitting) void handleRate(3);
          break;
        case "4":
          if (revealed && !submitting) void handleRate(4);
          break;
        case "Escape":
          router.push("/");
          break;
      }
    }

    window.addEventListener("keydown", onKey);
    return () => { window.removeEventListener("keydown", onKey); };
  }, [loading, done, fetchError, revealed, submitting, handleReveal, handleRate, router]);

  if (auth.status === "loading" || loading) {
    return (
      <div className="review-page">
        <p className="review-loading">Loading…</p>
      </div>
    );
  }

  if (auth.status === "unauthenticated") {
    return null;
  }

  if (fetchError !== null) {
    return (
      <div className="review-page">
        <div className="review-error" role="alert">
          Failed to load due cards: {fetchError}
        </div>
        <button
          className="btn btn-primary"
          onClick={() => { router.push("/"); }}
          type="button"
        >
          Return to Dashboard
        </button>
      </div>
    );
  }

  if (done) {
    return (
      <div className="review-page">
        <ReviewSessionSummary
          distribution={distribution}
          onExit={() => { router.push("/"); }}
          reviewed={reviewed}
          total={cards.length}
        />
      </div>
    );
  }

  const currentCard = cards[index];
  if (!currentCard) return null;

  return (
    <div className="review-page">
      <ReviewCard
        card={currentCard}
        error={cardError}
        index={index}
        onRate={(r) => { void handleRate(r); }}
        onReveal={handleReveal}
        revealed={revealed}
        submitting={submitting}
        total={cards.length}
      />
    </div>
  );
}
