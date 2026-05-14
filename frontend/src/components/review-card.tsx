import { Furigana } from "@/components/furigana";
import type { CardSentence, SrsCard } from "@/lib/api";

interface ReviewCardProps {
  card: SrsCard;
  index: number;
  total: number;
  revealed: boolean;
  submitting: boolean;
  error: string | null;
  onReveal: () => void;
  onRate: (rating: 1 | 2 | 3 | 4) => void;
}

const RATINGS: { value: 1 | 2 | 3 | 4; label: string; key: string; cls: string }[] = [
  { value: 1, label: "Again", key: "1", cls: "btn-again" },
  { value: 2, label: "Hard", key: "2", cls: "btn-hard" },
  { value: 3, label: "Good", key: "3", cls: "btn-good" },
  { value: 4, label: "Easy", key: "4", cls: "btn-easy" },
];

function ReviewSentences({ sentences }: { sentences: CardSentence[] }) {
  return (
    <ul className="review-sentences">
      {sentences.map((s, i) => (
        <li className="review-sentence-item" key={i}>
          <Furigana
            className="review-sentence-text"
            japanese={s.japanese}
            reading={s.reading || undefined}
          />
          {s.translation && (
            <p className="review-sentence-translation">{s.translation}</p>
          )}
        </li>
      ))}
    </ul>
  );
}

function GrammarAnswerBack({ card }: { card: SrsCard }) {
  return (
    <div className="review-card-back">
      {card.display_answer && (
        <p className="review-answer">{card.display_answer}</p>
      )}
      {card.display_formation && (
        <div className="review-formation">
          <span className="review-field-label">Formation</span>
          <span className="review-formation-text" lang="ja">
            {card.display_formation}
          </span>
        </div>
      )}
      {card.display_sentences && card.display_sentences.length > 0 && (
        <div className="review-examples">
          <span className="review-field-label">Examples</span>
          <ReviewSentences sentences={card.display_sentences} />
        </div>
      )}
    </div>
  );
}

function VocabAnswerBack({ card }: { card: SrsCard }) {
  return (
    <div className="review-card-back">
      {card.display_readings && card.display_readings.length > 0 && (
        <div className="review-readings">
          <span className="review-field-label">Readings</span>
          <span className="review-readings-text" lang="ja">
            {card.display_readings.join("、")}
          </span>
        </div>
      )}
      {card.display_answer && (
        <div className="review-meanings">
          <span className="review-field-label">Meanings</span>
          <p className="review-answer">{card.display_answer}</p>
        </div>
      )}
    </div>
  );
}

function FallbackAnswerBack({ card }: { card: SrsCard }) {
  return (
    <div className="review-card-back">
      <p className="review-answer">
        {card.display_answer ?? `${card.content_table} #${String(card.content_id)}`}
      </p>
    </div>
  );
}

function CardBack({ card }: { card: SrsCard }) {
  if (card.content_table === "grammar_points") {
    return <GrammarAnswerBack card={card} />;
  }
  if (card.content_table === "vocab_items") {
    return <VocabAnswerBack card={card} />;
  }
  return <FallbackAnswerBack card={card} />;
}

export function ReviewCard({
  card,
  index,
  total,
  revealed,
  submitting,
  error,
  onReveal,
  onRate,
}: ReviewCardProps) {
  const prompt =
    card.display_prompt ??
    `${card.card_type} #${String(card.content_id)}`;

  return (
    <div className="review-card">
      <div className="review-progress">
        Card {index + 1} of {total}
        <span className="review-state">{card.state}</span>
      </div>

      <div className="review-card-front">
        <p className="review-prompt" lang="ja">{prompt}</p>
      </div>

      {!revealed ? (
        <button
          className="btn review-reveal-btn"
          disabled={submitting}
          onClick={onReveal}
          type="button"
        >
          Reveal <kbd>Space</kbd>
        </button>
      ) : (
        <>
          <CardBack card={card} />

          <div className="review-rating-buttons">
            {RATINGS.map((r) => (
              <button
                className={`btn ${r.cls}`}
                disabled={submitting}
                key={r.value}
                onClick={() => { onRate(r.value); }}
                type="button"
              >
                {r.label}
                <kbd>{r.key}</kbd>
              </button>
            ))}
          </div>
        </>
      )}

      {error !== null && (
        <div className="review-error" role="alert">
          {error}
        </div>
      )}
    </div>
  );
}
