"use client";

import { useEffect, useState } from "react";
import { fetchRunning } from "@/lib/api";
import type { RunningResponse } from "@/lib/types";
import { round1, formatPace, formatHMTime } from "@/lib/format";
import PageShell from "@/components/PageShell";
import ScoreCard from "@/components/ScoreCard";
import Metric from "@/components/Metric";
import TrendChart from "@/components/TrendChart";
import styles from "./page.module.css";

export default function RunningPage() {
  const [data, setData] = useState<RunningResponse | null>(null);
  const [error, setError] = useState<string | null>(null);

  useEffect(() => {
    fetchRunning(undefined, 56)
      .then(setData)
      .catch((e: Error) => setError(e.message));
  }, []);

  if (error) {
    return (
      <PageShell title="Running">
        <p className={styles.error}>Failed to load: {error}</p>
      </PageShell>
    );
  }
  if (!data) {
    return (
      <PageShell title="Running">
        <p className={styles.loading}>Loading...</p>
      </PageShell>
    );
  }

  const { current, race_readiness_score, trend } = data;

  return (
    <PageShell title="Running" subtitle={data.date}>
      <ScoreCard title="Race Readiness" score={race_readiness_score}>
        {current && (
          <div className={styles.metricsGrid}>
            <Metric label="Weekly km" value={round1(current.weekly_km)} unit="km" />
            <Metric label="4-week rolling km" value={round1(current.rolling_4w_km)} unit="km" />
            <Metric label="Longest run (7d)" value={round1(current.longest_run_last_7d_km)} unit="km" />
            <Metric label="Easy pace (fixed HR)" value={formatPace(current.easy_pace_fixed_hr_sec_per_km)} />
            <Metric label="Quality sessions (14d)" value={String(current.quality_sessions_last_14d ?? "—")} />
            <Metric label="Projected HM" value={formatHMTime(current.projected_hm_time_sec)} />
            <Metric label="Plan adherence" value={current.plan_adherence_pct !== null ? `${Math.round(current.plan_adherence_pct)}%` : "—"} />
          </div>
        )}
      </ScoreCard>

      <TrendChart
        title="Weekly Kilometres"
        data={trend}
        series={[
          { key: "weekly_km", label: "Weekly km", color: "var(--color-blue)" },
          { key: "rolling_4w_km", label: "4-week avg", color: "var(--color-purple)" },
        ]}
      />

      <TrendChart
        title="Long Run Progression"
        data={trend}
        series={[
          { key: "longest_run_last_7d_km", label: "Longest run (7d)", color: "var(--color-teal)" },
        ]}
      />

      <TrendChart
        title="Easy Pace Efficiency"
        data={trend}
        series={[
          { key: "easy_pace_fixed_hr_sec_per_km", label: "sec/km at fixed HR", color: "var(--color-orange-chart)" },
        ]}
      />
    </PageShell>
  );
}
