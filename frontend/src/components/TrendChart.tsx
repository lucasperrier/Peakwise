"use client";

import {
  ResponsiveContainer,
  LineChart,
  Line,
  XAxis,
  YAxis,
  Tooltip,
  CartesianGrid,
} from "recharts";
import styles from "./TrendChart.module.css";

interface SeriesConfig {
  key: string;
  label: string;
  color: string;
}

interface TrendChartProps {
  title: string;
  // eslint-disable-next-line @typescript-eslint/no-explicit-any
  data: any[];
  series: SeriesConfig[];
  xKey?: string;
  height?: number;
}

function formatDateTick(value: string): string {
  const d = new Date(value);
  return `${d.getMonth() + 1}/${d.getDate()}`;
}

export default function TrendChart({
  title,
  data,
  series,
  xKey = "date",
  height = 240,
}: TrendChartProps) {
  if (data.length === 0) {
    return (
      <div className={styles.card}>
        <h3 className={styles.title}>{title}</h3>
        <p className={styles.empty}>No trend data available</p>
      </div>
    );
  }

  return (
    <div className={styles.card}>
      <h3 className={styles.title}>{title}</h3>
      <div className={styles.legend}>
        {series.map((s) => (
          <span key={s.key} className={styles.legendItem}>
            <span className={styles.legendDot} style={{ background: s.color }} />
            {s.label}
          </span>
        ))}
      </div>
      <ResponsiveContainer width="100%" height={height}>
        <LineChart data={data} margin={{ top: 4, right: 8, bottom: 4, left: 0 }}>
          <CartesianGrid strokeDasharray="3 3" stroke="var(--color-border)" />
          <XAxis
            dataKey={xKey}
            tickFormatter={formatDateTick}
            tick={{ fontSize: 11, fill: "var(--color-text-secondary)" }}
          />
          <YAxis
            tick={{ fontSize: 11, fill: "var(--color-text-secondary)" }}
            width={45}
          />
          <Tooltip
            contentStyle={{
              background: "var(--color-surface)",
              border: "1px solid var(--color-border)",
              borderRadius: 8,
              fontSize: 13,
            }}
          />
          {series.map((s) => (
            <Line
              key={s.key}
              dataKey={s.key}
              name={s.label}
              stroke={s.color}
              strokeWidth={2}
              dot={false}
              connectNulls
            />
          ))}
        </LineChart>
      </ResponsiveContainer>
    </div>
  );
}
