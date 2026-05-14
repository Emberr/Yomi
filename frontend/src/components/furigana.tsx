interface FuriganaProps {
  japanese: string;
  reading?: string;
  className?: string;
}

/**
 * A reading is considered kana (suitable for ruby) when it contains no
 * Latin letters. Romaji readings contain [a-zA-Z] and must not be rendered
 * as <ruby> furigana.
 */
function isKanaReading(s: string): boolean {
  return !/[a-zA-Z]/.test(s);
}

/**
 * Renders Japanese text with an optional reading annotation.
 *
 * - If reading is kana-only: renders as <ruby> with <rt> (proper furigana).
 * - If reading contains Latin letters (romaji): renders as plain secondary
 *   text labelled "Reading:" — not as ruby, because romaji is not furigana.
 * - If no reading: renders plain Japanese span.
 *
 * Phase 5 will upgrade kana furigana to per-token ruby via the live parser.
 * Never uses dangerouslySetInnerHTML.
 */
export function Furigana({ japanese, reading, className }: FuriganaProps) {
  if (reading) {
    if (isKanaReading(reading)) {
      return (
        <ruby className={className} lang="ja">
          {japanese}
          <rt>{reading}</rt>
        </ruby>
      );
    }
    // Romaji or mixed — show as secondary reading text, not ruby.
    return (
      <span className={className}>
        <span lang="ja">{japanese}</span>
        <span className="reading-annotation">
          <span className="reading-label">Reading:</span> {reading}
        </span>
      </span>
    );
  }
  return (
    <span className={className} lang="ja">
      {japanese}
    </span>
  );
}
