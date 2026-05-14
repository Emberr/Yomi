import Link from "next/link";

interface ReviewSessionSummaryProps {
  reviewed: number;
  total: number;
  distribution: Record<1 | 2 | 3 | 4, number>;
  onExit: () => void;
}

const RATING_LABELS: Record<1 | 2 | 3 | 4, string> = {
  1: "Again",
  2: "Hard",
  3: "Good",
  4: "Easy",
};

export function ReviewSessionSummary({
  reviewed,
  total,
  distribution,
  onExit,
}: ReviewSessionSummaryProps) {
  const isEmpty = total === 0;

  return (
    <div className="review-summary">
      <h1 className="review-summary-title">
        {isEmpty ? "No reviews due" : "Session complete"}
      </h1>

      {isEmpty ? (
        <p className="review-summary-empty">
          No cards are due right now. Add more content to your review queue:
        </p>
      ) : (
        <>
          <p className="review-summary-count">
            Reviewed {reviewed} of {total} cards
          </p>

          <table className="review-summary-table">
            <thead>
              <tr>
                <th>Rating</th>
                <th>Count</th>
              </tr>
            </thead>
            <tbody>
              {([1, 2, 3, 4] as const).map((r) => (
                <tr key={r}>
                  <td>{RATING_LABELS[r]}</td>
                  <td>{distribution[r]}</td>
                </tr>
              ))}
            </tbody>
          </table>
        </>
      )}

      <div className="review-summary-links">
        <Link className="btn btn-link" href="/grammar">
          Browse Grammar
        </Link>
        <Link className="btn btn-link" href="/vocabulary">
          Browse Vocabulary
        </Link>
      </div>

      <button className="btn btn-primary" onClick={onExit} type="button">
        Return to Dashboard
      </button>
    </div>
  );
}
