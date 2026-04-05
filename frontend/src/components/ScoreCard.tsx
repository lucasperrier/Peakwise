"use client";

import { scoreColor, scoreLabel } from "@/lib/format";
import styles from "./ScoreCard.module.css";

interface ScoreCardProps {
  title: string;
  score: number | null;
  compact?: boolean;
  children?: React.ReactNode;
}

function scoreRingOffset(score: number | null): number {
  if (score === null) return 282.7;
  const pct = Math.max(0, Math.min(100, score)) / 100;
  return 282.7 * (1 - pct);
}

export default function ScoreCard({ title, score, compact, children }: ScoreCardProps) {
  const color = scoreColor(score);

  return (
    <div className={`${styles.card} ${compact ? styles.compact : ""}`}>
      <div className={styles.header}>
        <div className={styles.ringWrap}>
          <svg viewBox="0 0 100 100" className={styles.ring}>
            <circle
              cx="50" cy="50" r="45"
              fill="none"
              stroke="var(--color-border)"
              strokeWidth="5"
            />
            <circle
              cx="50" cy="50" r="45"
              fill="none"
              stroke={color}
              strokeWidth="5"
              strokeLinecap="round"
              strokeDasharray="282.7"
              strokeDashoffset={scoreRingOffset(score)}
              transform="rotate(-90 50 50)"
              className={styles.ringProgress}
            />
          </svg>
          <div className={styles.ringCenter}>
            <span className={styles.score} style={{ color }}>{score !== null ? Math.round(score) : "—"}</span>
          </div>
        </div>
        <div className={styles.titleGroup}>
          <h3 className={styles.title}>{title}</h3>
          <span className={styles.label} style={{ color }}>{scoreLabel(score)}</span>
        </div>
      </div>
      {children && <div className={styles.body}>{children}</div>}
    </div>
  );
}
