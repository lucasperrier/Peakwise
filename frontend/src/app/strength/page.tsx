"use client";

import { useEffect, useState } from "react";
import { fetchStrength } from "@/lib/api";
import type { StrengthResponse } from "@/lib/types";
import { round1, round0 } from "@/lib/format";
import PageShell from "@/components/PageShell";
import ScoreCard from "@/components/ScoreCard";
import Metric from "@/components/Metric";
import TrendChart from "@/components/TrendChart";
import styles from "./page.module.css";

export default function StrengthPage() {
  const [data, setData] = useState<StrengthResponse | null>(null);
  const [error, setError] = useState<string | null>(null);

  useEffect(() => {
    fetchStrength(undefined, 56)
      .then(setData)
      .catch((e: Error) => setError(e.message));
  }, []);

  if (error) {
    return (
      <PageShell title="Strength">
        <p className={styles.error}>Failed to load: {error}</p>
      </PageShell>
    );
  }
  if (!data) {
    return (
      <PageShell title="Strength">
        <p className={styles.loading}>Loading...</p>
      </PageShell>
    );
  }

  const { current, load_balance_score, recent_workouts, trend } = data;

  return (
    <PageShell title="Strength" subtitle={data.date}>
      <ScoreCard title="Training Balance" score={load_balance_score}>
        {current && (
          <div className={styles.metricsGrid}>
            <Metric label="Hard days (7d)" value={String(current.hard_day_count_7d ?? "—")} />
            <Metric label="Lower-body CF density" value={round1(current.lower_body_crossfit_density_7d)} />
            <Metric label="Long-run protection" value={round0(current.long_run_protection_score)} />
            <Metric label="Interference risk" value={round0(current.interference_risk_score)} />
          </div>
        )}
      </ScoreCard>

      {/* Recent workouts timeline */}
      {recent_workouts.length > 0 && (
        <div className={styles.workoutSection}>
          <h3 className={styles.sectionTitle}>Recent Sessions</h3>
          <div className={styles.workoutList}>
            {recent_workouts.map((w) => (
              <div key={w.workout_id} className={styles.workoutItem}>
                <div className={styles.workoutDate}>{w.session_date}</div>
                <div className={styles.workoutInfo}>
                  <span className={styles.workoutType}>{w.session_type}</span>
                  {w.duration_min !== null && (
                    <span className={styles.workoutDetail}>{Math.round(w.duration_min)} min</span>
                  )}
                  {w.training_load !== null && (
                    <span className={styles.workoutDetail}>Load: {round0(w.training_load)}</span>
                  )}
                  {w.is_lower_body_dominant && (
                    <span className={styles.lowerBodyTag}>Lower body</span>
                  )}
                </div>
                {w.raw_notes && <p className={styles.workoutNotes}>{w.raw_notes}</p>}
              </div>
            ))}
          </div>
        </div>
      )}

      <TrendChart
        title="Hard Day Count (7-day)"
        data={trend}
        series={[
          { key: "hard_day_count_7d", label: "Hard days", color: "var(--color-orange-chart)" },
        ]}
      />

      <TrendChart
        title="Lower-Body Load Density"
        data={trend}
        series={[
          { key: "lower_body_crossfit_density_7d", label: "LB CF density", color: "var(--color-purple)" },
          { key: "interference_risk_score", label: "Interference risk", color: "var(--color-red)" },
        ]}
      />
    </PageShell>
  );
}
