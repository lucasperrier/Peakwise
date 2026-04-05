/** Shared formatting helpers. */

export function scoreColor(score: number | null): string {
  if (score === null) return "var(--color-muted)";
  if (score >= 85) return "var(--color-green)";
  if (score >= 70) return "var(--color-light-green)";
  if (score >= 55) return "var(--color-yellow)";
  if (score >= 40) return "var(--color-orange)";
  return "var(--color-red)";
}

export function scoreLabel(score: number | null): string {
  if (score === null) return "No data";
  if (score >= 85) return "Strong";
  if (score >= 70) return "Stable";
  if (score >= 55) return "Caution";
  if (score >= 40) return "High caution";
  return "Poor";
}

export function formatMode(mode: string): string {
  return mode.replace(/_/g, " ").replace(/\b\w/g, (c) => c.toUpperCase());
}

export function formatAction(action: string): string {
  return action.replace(/_/g, " ").replace(/\b\w/g, (c) => c.toUpperCase());
}

export function formatPace(secPerKm: number | null): string {
  if (secPerKm === null) return "—";
  const min = Math.floor(secPerKm / 60);
  const sec = Math.round(secPerKm % 60);
  return `${min}:${sec.toString().padStart(2, "0")} /km`;
}

export function formatHMTime(sec: number | null): string {
  if (sec === null) return "—";
  const h = Math.floor(sec / 3600);
  const m = Math.floor((sec % 3600) / 60);
  const s = Math.round(sec % 60);
  return `${h}:${m.toString().padStart(2, "0")}:${s.toString().padStart(2, "0")}`;
}

export function formatMinutesToHours(min: number | null): string {
  if (min === null) return "—";
  const h = Math.floor(min / 60);
  const m = Math.round(min % 60);
  return `${h}h ${m}m`;
}

export function round1(v: number | null): string {
  if (v === null) return "—";
  return v.toFixed(1);
}

export function round0(v: number | null): string {
  if (v === null) return "—";
  return Math.round(v).toString();
}
