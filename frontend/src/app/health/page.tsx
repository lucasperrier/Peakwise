"use client";

import { useEffect, useState } from "react";
import { fetchHealth } from "@/lib/api";
import type { HealthResponse } from "@/lib/types";
import { round1, round0, formatMinutesToHours } from "@/lib/format";
import PageShell from "@/components/PageShell";
import ScoreCard from "@/components/ScoreCard";
import Metric from "@/components/Metric";
import TrendChart from "@/components/TrendChart";
import styles from "./page.module.css";

export default function HealthPage() {
  const [data, setData] = useState<HealthResponse | null>(null);
  const [error, setError] = useState<string | null>(null);

  useEffect(() => {
    fetchHealth(undefined, 56)
      .then(setData)
      .catch((e: Error) => setError(e.message));
  }, []);

  if (error) {
    return (
      <PageShell title="Health">
        <p className={styles.error}>Failed to load: {error}</p>
      </PageShell>
    );
  }
  if (!data) {
    return (
      <PageShell title="Health">
        <p className={styles.loading}>Loading...</p>
      </PageShell>
    );
  }

  const { current, general_health_score, trend } = data;

  return (
    <PageShell title="Health" subtitle={data.date}>
      <ScoreCard title="General Health" score={general_health_score}>
        {current && (
          <div className={styles.metricsGrid}>
            <Metric label="Weight (7d avg)" value={round1(current.body_weight_7d_avg)} unit="kg" />
            <Metric label="Weight slope (28d)" value={round1(current.body_weight_28d_slope)} unit="kg/wk" />
            <Metric label="Sleep (7d avg)" value={current.sleep_7d_avg !== null ? formatMinutesToHours(current.sleep_7d_avg) : "—"} />
            <Metric label="Sleep debt" value={current.sleep_debt_min !== null ? formatMinutesToHours(current.sleep_debt_min) : "—"} />
            <Metric label="HRV (7d avg)" value={round1(current.hrv_7d_avg)} unit="ms" />
            <Metric label="Resting HR (7d)" value={round0(current.resting_hr_7d_avg)} unit="bpm" />
            <Metric label="Sleep consistency" value={round0(current.sleep_consistency_score)} />
            <Metric label="Steps consistency" value={round0(current.steps_consistency_score)} />
            <Metric label="Pain-free days (14d)" value={String(current.pain_free_days_last_14d ?? "—")} />
            <Metric label="Mood trend" value={round1(current.mood_trend)} />
            <Metric label="Stress trend" value={round1(current.stress_trend)} />
          </div>
        )}
      </ScoreCard>

      <TrendChart
        title="Weight (7-day average)"
        data={trend}
        series={[
          { key: "body_weight_7d_avg", label: "Weight", color: "var(--color-purple)" },
        ]}
      />

      <TrendChart
        title="Sleep (7-day average)"
        data={trend}
        series={[
          { key: "sleep_7d_avg", label: "Sleep (min)", color: "var(--color-blue)" },
          { key: "sleep_debt_min", label: "Sleep debt (min)", color: "var(--color-red)" },
        ]}
      />

      <TrendChart
        title="HRV & Resting HR"
        data={trend}
        series={[
          { key: "hrv_7d_avg", label: "HRV (ms)", color: "var(--color-teal)" },
          { key: "resting_hr_7d_avg", label: "Resting HR (bpm)", color: "var(--color-orange-chart)" },
        ]}
      />

      <TrendChart
        title="Mood & Stress"
        data={trend}
        series={[
          { key: "mood_trend", label: "Mood", color: "var(--color-green)" },
          { key: "stress_trend", label: "Stress", color: "var(--color-red)" },
        ]}
      />
    </PageShell>
  );
}
