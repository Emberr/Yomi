interface JlptBadgeProps {
  level: string;
}

const LEVEL_CLASS: Record<string, string> = {
  N5: "jlpt-badge jlpt-n5",
  N4: "jlpt-badge jlpt-n4",
  N3: "jlpt-badge jlpt-n3",
  N2: "jlpt-badge jlpt-n2",
  N1: "jlpt-badge jlpt-n1",
};

export function JlptBadge({ level }: JlptBadgeProps) {
  const cls = LEVEL_CLASS[level] ?? "jlpt-badge jlpt-unknown";
  return <span className={cls}>{level}</span>;
}
