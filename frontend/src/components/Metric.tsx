"use client";

import styles from "./Metric.module.css";

interface MetricProps {
  label: string;
  value: string;
  unit?: string;
  small?: boolean;
}

export default function Metric({ label, value, unit, small }: MetricProps) {
  return (
    <div className={`${styles.metric} ${small ? styles.small : ""}`}>
      <span className={styles.label}>{label}</span>
      <span className={styles.value}>
        {value}
        {unit && <span className={styles.unit}> {unit}</span>}
      </span>
    </div>
  );
}
