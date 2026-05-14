interface FuriganaProps {
  japanese: string;
  reading?: string;
  className?: string;
}

/**
 * Renders Japanese text with an optional reading annotation.
 * Phase 3: shows reading as a ruby annotation over the full sentence.
 * Phase 5 will upgrade to per-token ruby using the live parser.
 * Never uses dangerouslySetInnerHTML.
 */
export function Furigana({ japanese, reading, className }: FuriganaProps) {
  if (reading) {
    return (
      <ruby className={className} lang="ja">
        {japanese}
        <rt>{reading}</rt>
      </ruby>
    );
  }
  return (
    <span className={className} lang="ja">
      {japanese}
    </span>
  );
}
