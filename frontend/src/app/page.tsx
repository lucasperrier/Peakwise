"use client";

import { useEffect, useState, FormEvent } from "react";
import { fetchToday, askQuestion } from "@/lib/api";
import type { TodayResponse } from "@/lib/types";
import { formatAction, formatMode, round0 } from "@/lib/format";
import PageShell from "@/components/PageShell";
import ScoreCard from "@/components/ScoreCard";
import WarningBadge from "@/components/WarningBadge";
import Metric from "@/components/Metric";
import styles from "./page.module.css";

export default function TodayPage() {
  const [data, setData] = useState<TodayResponse | null>(null);
  const [error, setError] = useState<string | null>(null);

  // Ask Peakwise state
  const [question, setQuestion] = useState("");
  const [answer, setAnswer] = useState<string | null>(null);
  const [askLoading, setAskLoading] = useState(false);

  useEffect(() => {
    fetchToday()
      .then(setData)
      .catch((e: Error) => setError(e.message));
  }, []);

  const handleAsk = async (e: FormEvent) => {
    e.preventDefault();
    const q = question.trim();
    if (!q) return;
    setAskLoading(true);
    setAnswer(null);
    try {
      const res = await askQuestion({ question: q, date: data?.date ?? undefined });
      setAnswer(res.answer);
    } catch {
      setAnswer("Sorry, I couldn't get an answer right now.");
    } finally {
      setAskLoading(false);
    }
  };

  if (error) {
    return (
      <PageShell title="Today">
        <p className={styles.error}>Failed to load: {error}</p>
      </PageShell>
    );
  }

  if (!data) {
    return (
      <PageShell title="Today">
        <div className={styles.loadingWrap}>
          <div className={styles.spinner} />
          <p className={styles.loading}>Loading your day...</p>
        </div>
      </PageShell>
    );
  }

  const { recommendation, scores, subcomponents, warnings } = data;

  return (
    <PageShell title="Today" subtitle={data.date}>
      {/* Warnings */}
      {warnings && <WarningBadge warnings={warnings} />}

      {/* Recommendation hero */}
      {recommendation && (
        <div className={styles.hero}>
          <div className={styles.heroTop}>
            <span className={styles.heroMode}>{formatMode(recommendation.mode)}</span>
            {recommendation.risk_flags.length > 0 && (
              <div className={styles.riskFlags}>
                {recommendation.risk_flags.map((f) => (
                  <span key={f} className={styles.riskFlag}>{f.replace(/_/g, " ")}</span>
                ))}
              </div>
            )}
          </div>
          <h2 className={styles.heroAction}>{formatAction(recommendation.recommended_action)}</h2>
          <div className={styles.heroMeta}>
            {recommendation.intensity_modifier && (
              <span className={styles.tag}>🔥 {recommendation.intensity_modifier}</span>
            )}
            {recommendation.duration_modifier && (
              <span className={styles.tag}>⏱ {recommendation.duration_modifier}</span>
            )}
            {recommendation.next_best_alternative && (
              <span className={styles.tagAlt}>
                or {formatAction(recommendation.next_best_alternative)}
              </span>
            )}
          </div>
          {recommendation.reason_codes.length > 0 && (
            <div className={styles.reasons}>
              {recommendation.reason_codes.map((r) => (
                <span key={r} className={styles.reasonCode}>{r.replace(/_/g, " ")}</span>
              ))}
            </div>
          )}
        </div>
      )}

      {/* LLM Explanation */}
      {data.explanation && (
        <div className={styles.aiCard}>
          <div className={styles.aiHeader}>
            <span className={styles.aiIcon}>✦</span>
            <span className={styles.aiLabel}>AI Analysis</span>
          </div>
          <p className={styles.aiText}>{data.explanation}</p>
        </div>
      )}

      {/* Score cards */}
      <div className={styles.grid}>
        <ScoreCard title="Recovery" score={scores?.recovery ?? null} compact>
          <SubcomponentList sub={subcomponents?.recovery} />
        </ScoreCard>

        <ScoreCard title="Half-Marathon" score={scores?.race_readiness ?? null} compact>
          <SubcomponentList sub={subcomponents?.race_readiness} />
        </ScoreCard>

        <ScoreCard title="Health" score={scores?.general_health ?? null} compact>
          <SubcomponentList sub={subcomponents?.general_health} />
        </ScoreCard>

        <ScoreCard title="Training Balance" score={scores?.load_balance ?? null} compact>
          <SubcomponentList sub={subcomponents?.load_balance} />
        </ScoreCard>
      </div>

      {/* Score Drivers */}
      {subcomponents && (
        <div className={styles.driversCard}>
          <h3 className={styles.driversTitle}>Score Drivers</h3>
          <ExplanationSummary subcomponents={subcomponents} />
        </div>
      )}

      {/* Ask Peakwise */}
      <div className={styles.askCard}>
        <h3 className={styles.askTitle}>Ask Peakwise</h3>
        <form onSubmit={handleAsk} className={styles.askForm}>
          <input
            type="text"
            className={styles.askInput}
            placeholder="e.g. Should I run long today?"
            value={question}
            onChange={(e) => setQuestion(e.target.value)}
            disabled={askLoading}
          />
          <button type="submit" className={styles.askBtn} disabled={askLoading || !question.trim()}>
            {askLoading ? "…" : "Ask"}
          </button>
        </form>
        {answer && (
          <div className={styles.askAnswer}>
            <span className={styles.aiIcon}>✦</span>
            <p>{answer}</p>
          </div>
        )}
      </div>
    </PageShell>
  );
}

function SubcomponentList({ sub }: { sub?: Record<string, number | null> }) {
  if (!sub) return null;
  const entries = Object.entries(sub).filter(([, v]) => v !== null);
  if (entries.length === 0) return null;
  return (
    <div className={styles.subList}>
      {entries.map(([k, v]) => (
        <Metric key={k} label={k.replace(/_/g, " ")} value={round0(v)} small />
      ))}
    </div>
  );
}

function ExplanationSummary({
  subcomponents,
}: {
  subcomponents: NonNullable<TodayResponse["subcomponents"]>;
}) {
  const items: { category: string; name: string; value: number; positive: boolean }[] = [];

  for (const [cat, subs] of Object.entries(subcomponents)) {
    for (const [name, value] of Object.entries(subs)) {
      if (value !== null) {
        items.push({ category: cat, name, value, positive: value >= 60 });
      }
    }
  }

  const positives = items.filter((i) => i.positive).sort((a, b) => b.value - a.value).slice(0, 3);
  const negatives = items.filter((i) => !i.positive).sort((a, b) => a.value - b.value).slice(0, 3);

  return (
    <div className={styles.driversGrid}>
      {positives.length > 0 && (
        <div>
          <h4 className={styles.driversSubtitle}>Strengths</h4>
          <ul className={styles.driverList}>
            {positives.map((i) => (
              <li key={`${i.category}-${i.name}`} className={styles.driverPositive}>
                {i.name.replace(/_/g, " ")} — {round0(i.value)}
              </li>
            ))}
          </ul>
        </div>
      )}
      {negatives.length > 0 && (
        <div>
          <h4 className={styles.driversSubtitle}>Watch</h4>
          <ul className={styles.driverList}>
            {negatives.map((i) => (
              <li key={`${i.category}-${i.name}`} className={styles.driverNegative}>
                {i.name.replace(/_/g, " ")} — {round0(i.value)}
              </li>
            ))}
          </ul>
        </div>
      )}
    </div>
  );
}
