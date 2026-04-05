"use client";

import styles from "./WarningBadge.module.css";

const WARNING_LABELS: Record<string, string> = {
  knee_pain_warning: "Knee pain",
  illness_warning: "Illness",
  sleep_debt_warning: "Sleep debt",
  hrv_suppression_warning: "HRV suppressed",
  resting_hr_spike_warning: "HR elevated",
  aggressive_weight_loss_warning: "Weight loss",
  overload_warning: "Overload",
};

interface WarningBadgeProps {
  warnings: Record<string, boolean>;
}

export default function WarningBadge({ warnings }: WarningBadgeProps) {
  const active = Object.entries(warnings).filter(([, v]) => v);
  if (active.length === 0) return null;
  return (
    <div className={styles.wrap}>
      {active.map(([key]) => (
        <span key={key} className={styles.badge}>
          {WARNING_LABELS[key] ?? key.replace(/_/g, " ")}
        </span>
      ))}
    </div>
  );
}
