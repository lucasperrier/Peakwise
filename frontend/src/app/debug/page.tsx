"use client";

import { useEffect, useState } from "react";
import { fetchDebugDay } from "@/lib/api";
import type { DebugDayResponse } from "@/lib/types";
import { confidenceColor, confidenceLabel } from "@/lib/format";
import PageShell from "@/components/PageShell";
import styles from "./page.module.css";

export default function DebugPage() {
  const [date, setDate] = useState(() => new Date().toISOString().slice(0, 10));
  const [data, setData] = useState<DebugDayResponse | null>(null);
  const [error, setError] = useState<string | null>(null);
  const [loading, setLoading] = useState(false);

  const load = (d: string) => {
    setLoading(true);
    setError(null);
    fetchDebugDay(d)
      .then(setData)
      .catch((e: Error) => setError(e.message))
      .finally(() => setLoading(false));
  };

  useEffect(() => {
    load(date);
  }, []);

  const handleSubmit = (e: React.FormEvent) => {
    e.preventDefault();
    load(date);
  };

  return (
    <PageShell title="Debug" subtitle="Day inspector">
      <form onSubmit={handleSubmit} className={styles.form}>
        <input
          type="date"
          value={date}
          onChange={(e) => setDate(e.target.value)}
          className={styles.dateInput}
        />
        <button type="submit" className={styles.loadBtn} disabled={loading}>
          {loading ? "Loading…" : "Load"}
        </button>
      </form>

      {error && <p className={styles.error}>{error}</p>}

      {data && (
        <div className={styles.sections}>
          {/* Confidence */}
          <Section title="Decision Confidence">
            <div className={styles.confidenceRow}>
              <span
                className={styles.confDot}
                style={{ background: confidenceColor(data.confidence?.level) }}
              />
              <span>{confidenceLabel(data.confidence?.level)}</span>
              <span className={styles.confScore}>{data.confidence?.score}%</span>
            </div>
          </Section>

          {/* Source Coverage */}
          <Section title="Source Coverage">
            <div className={styles.kvGrid}>
              {Object.entries(data.source_coverage || {}).map(([k, v]) => (
                <div key={k} className={styles.kvRow}>
                  <span className={styles.kvKey}>{k}</span>
                  <span className={v ? styles.kvTrue : styles.kvFalse}>{v ? "✓" : "✗"}</span>
                </div>
              ))}
            </div>
          </Section>

          {/* Field Provenance */}
          <Section title="Field Provenance">
            <div className={styles.kvGrid}>
              {Object.entries(data.field_provenance || {}).map(([k, v]) => (
                <div key={k} className={styles.kvRow}>
                  <span className={styles.kvKey}>{k}</span>
                  <span className={styles.kvVal}>{v ?? "—"}</span>
                </div>
              ))}
            </div>
          </Section>

          {/* Score Components */}
          {data.score_components.length > 0 && (
            <Section title="Score Components">
              <table className={styles.table}>
                <thead>
                  <tr>
                    <th>Score</th>
                    <th>Component</th>
                    <th>Raw</th>
                    <th>Norm</th>
                    <th>Weighted</th>
                    <th>Dir</th>
                  </tr>
                </thead>
                <tbody>
                  {data.score_components.map((c, i) => (
                    <tr key={i}>
                      <td>{c.score_type}</td>
                      <td>{c.component_name.replace(/_/g, " ")}</td>
                      <td>{c.raw_input_value?.toFixed(1) ?? "—"}</td>
                      <td>{c.normalized_value?.toFixed(1) ?? "—"}</td>
                      <td>{c.weighted_contribution?.toFixed(2) ?? "—"}</td>
                      <td className={
                        c.direction === "positive" ? styles.dirPos :
                        c.direction === "negative" ? styles.dirNeg : styles.dirNeu
                      }>
                        {c.direction === "positive" ? "▲" : c.direction === "negative" ? "▼" : "—"}
                      </td>
                    </tr>
                  ))}
                </tbody>
              </table>
            </Section>
          )}

          {/* Reason Codes */}
          {data.reason_codes.length > 0 && (
            <Section title="Reason Codes">
              <div className={styles.codeList}>
                {data.reason_codes.map((r, i) => (
                  <div key={i} className={styles.codeRow}>
                    <span className={styles.codeBadge}>{r.code}</span>
                    <span className={styles.codeSrc}>{r.source}</span>
                    {r.severity && <span className={styles.codeSev}>{r.severity}</span>}
                    {r.detail && <span className={styles.codeDetail}>{r.detail}</span>}
                  </div>
                ))}
              </div>
            </Section>
          )}

          {/* Recommendation */}
          {data.recommendation && (
            <Section title="Recommendation">
              <JsonBlock data={data.recommendation} />
            </Section>
          )}

          {/* Daily Facts */}
          {data.daily_facts && (
            <Section title="Daily Facts">
              <JsonBlock data={data.daily_facts} />
            </Section>
          )}

          {/* Features */}
          {data.features && (
            <Section title="Features">
              <JsonBlock data={data.features} />
            </Section>
          )}

          {/* Baselines */}
          {Object.keys(data.baselines).length > 0 && (
            <Section title="Baselines">
              <JsonBlock data={data.baselines} />
            </Section>
          )}

          {/* Workouts in lookback */}
          {data.workouts_in_lookback.length > 0 && (
            <Section title={`Workouts (${data.workouts_in_lookback.length})`}>
              <JsonBlock data={data.workouts_in_lookback} />
            </Section>
          )}
        </div>
      )}
    </PageShell>
  );
}

function Section({ title, children }: { title: string; children: React.ReactNode }) {
  const [open, setOpen] = useState(true);
  return (
    <div className={styles.section}>
      <button className={styles.sectionToggle} onClick={() => setOpen(!open)}>
        <span className={styles.sectionArrow}>{open ? "▾" : "▸"}</span>
        <h3 className={styles.sectionTitle}>{title}</h3>
      </button>
      {open && <div className={styles.sectionBody}>{children}</div>}
    </div>
  );
}

function JsonBlock({ data }: { data: unknown }) {
  return (
    <pre className={styles.json}>{JSON.stringify(data, null, 2)}</pre>
  );
}
