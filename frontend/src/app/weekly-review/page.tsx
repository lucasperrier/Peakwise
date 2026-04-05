"use client";

import { useEffect, useState } from "react";
import { fetchWeeklyReview } from "@/lib/api";
import type { WeeklyReviewResponse, ScoreChange } from "@/lib/types";
import { round1, round0, formatMinutesToHours } from "@/lib/format";
import { scoreColor } from "@/lib/format";
import PageShell from "@/components/PageShell";
import styles from "./page.module.css";

export default function WeeklyReviewPage() {
  const [data, setData] = useState<WeeklyReviewResponse | null>(null);
  const [error, setError] = useState<string | null>(null);

  useEffect(() => {
    fetchWeeklyReview()
      .then(setData)
      .catch((e: Error) => setError(e.message));
  }, []);

  if (error) {
    return (
      <PageShell title="Weekly Review">
        <p className={styles.error}>Failed to load: {error}</p>
      </PageShell>
    );
  }
  if (!data) {
    return (
      <PageShell title="Weekly Review">
        <p className={styles.loading}>Loading...</p>
      </PageShell>
    );
  }

  const { current_week, previous_week, score_changes, flags } = data;

  return (
    <PageShell
      title="Weekly Review"
      subtitle={`${current_week.start_date} — ${current_week.end_date}`}
    >
      {/* Flags */}
      {flags.length > 0 && (
        <div className={styles.flagsWrap}>
          {flags.map((f) => (
            <span key={f} className={styles.flag}>
              {f.replace(/_/g, " ")}
            </span>
          ))}
        </div>
      )}

      {/* LLM Explanation */}
      {data.explanation && (
        <div className={styles.aiCard}>
          <div className={styles.aiHeader}>
            <span className={styles.aiIcon}>✦</span>
            <span className={styles.aiLabel}>Weekly AI Summary</span>
          </div>
          <p className={styles.aiText}>{data.explanation}</p>
        </div>
      )}

      {/* Score changes */}
      {score_changes && (
        <div className={styles.changesGrid}>
          <ChangeCard label="Recovery" change={score_changes.recovery} />
          <ChangeCard label="Race Readiness" change={score_changes.race_readiness} />
          <ChangeCard label="Health" change={score_changes.general_health} />
          <ChangeCard label="Balance" change={score_changes.load_balance} />
        </div>
      )}

      {/* Week summary comparison */}
      <div className={styles.comparisonSection}>
        <h3 className={styles.sectionTitle}>This Week</h3>
        <div className={styles.summaryGrid}>
          <SummaryItem label="Total km" value={round1(current_week.total_km)} />
          <SummaryItem label="Workouts" value={String(current_week.workout_count)} />
          <SummaryItem label="Avg sleep" value={current_week.avg_sleep_duration_min !== null ? formatMinutesToHours(current_week.avg_sleep_duration_min) : "—"} />
          <SummaryItem label="Avg HRV" value={round1(current_week.avg_hrv_ms)} unit="ms" />
          <SummaryItem label="Avg resting HR" value={round0(current_week.avg_resting_hr_bpm)} unit="bpm" />
        </div>
      </div>

      {previous_week && (
        <div className={styles.comparisonSection}>
          <h3 className={styles.sectionTitle}>Previous Week</h3>
          <div className={styles.summaryGrid}>
            <SummaryItem label="Total km" value={round1(previous_week.total_km)} />
            <SummaryItem label="Workouts" value={String(previous_week.workout_count)} />
            <SummaryItem label="Avg sleep" value={previous_week.avg_sleep_duration_min !== null ? formatMinutesToHours(previous_week.avg_sleep_duration_min) : "—"} />
            <SummaryItem label="Avg HRV" value={round1(previous_week.avg_hrv_ms)} unit="ms" />
            <SummaryItem label="Avg resting HR" value={round0(previous_week.avg_resting_hr_bpm)} unit="bpm" />
          </div>
        </div>
      )}
    </PageShell>
  );
}

function ChangeCard({ label, change }: { label: string; change: ScoreChange | null }) {
  if (!change) return null;
  const deltaStr =
    change.delta !== null
      ? `${change.delta > 0 ? "+" : ""}${round1(change.delta)}`
      : "—";
  const deltaColor =
    change.delta !== null
      ? change.delta > 0
        ? "var(--color-green)"
        : change.delta < -5
          ? "var(--color-red)"
          : "var(--color-text-secondary)"
      : "var(--color-text-secondary)";

  return (
    <div className={styles.changeCard}>
      <span className={styles.changeLabel}>{label}</span>
      <span
        className={styles.changeCurrent}
        style={{ color: scoreColor(change.current) }}
      >
        {change.current !== null ? round0(change.current) : "—"}
      </span>
      <span className={styles.changeDelta} style={{ color: deltaColor }}>
        {deltaStr}
      </span>
    </div>
  );
}

function SummaryItem({ label, value, unit }: { label: string; value: string; unit?: string }) {
  return (
    <div className={styles.summaryItem}>
      <span className={styles.summaryLabel}>{label}</span>
      <span className={styles.summaryValue}>
        {value}
        {unit && <span className={styles.summaryUnit}> {unit}</span>}
      </span>
    </div>
  );
}
