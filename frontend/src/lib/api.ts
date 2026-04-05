/** API client for Peakwise backend. */

import type {
  AskRequest,
  AskResponse,
  HealthResponse,
  RunningResponse,
  StrengthResponse,
  TodayResponse,
  WeeklyReviewResponse,
} from "./types";

const API_BASE = process.env.NEXT_PUBLIC_API_URL ?? "http://localhost:8000/api";

async function fetchJSON<T>(path: string): Promise<T> {
  const res = await fetch(`${API_BASE}${path}`, { cache: "no-store" });
  if (!res.ok) {
    throw new Error(`API ${path} returned ${res.status}`);
  }
  return res.json() as Promise<T>;
}

async function postJSON<T>(path: string, body: unknown): Promise<T> {
  const res = await fetch(`${API_BASE}${path}`, {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify(body),
  });
  if (!res.ok) {
    throw new Error(`API ${path} returned ${res.status}`);
  }
  return res.json() as Promise<T>;
}

export function fetchToday(date?: string): Promise<TodayResponse> {
  const q = date ? `?date=${date}` : "";
  return fetchJSON<TodayResponse>(`/today${q}`);
}

export function fetchRunning(date?: string, days?: number): Promise<RunningResponse> {
  const params = new URLSearchParams();
  if (date) params.set("date", date);
  if (days) params.set("days", String(days));
  const q = params.toString() ? `?${params}` : "";
  return fetchJSON<RunningResponse>(`/running${q}`);
}

export function fetchHealth(date?: string, days?: number): Promise<HealthResponse> {
  const params = new URLSearchParams();
  if (date) params.set("date", date);
  if (days) params.set("days", String(days));
  const q = params.toString() ? `?${params}` : "";
  return fetchJSON<HealthResponse>(`/health${q}`);
}

export function fetchStrength(date?: string, days?: number): Promise<StrengthResponse> {
  const params = new URLSearchParams();
  if (date) params.set("date", date);
  if (days) params.set("days", String(days));
  const q = params.toString() ? `?${params}` : "";
  return fetchJSON<StrengthResponse>(`/strength${q}`);
}

export function fetchWeeklyReview(date?: string): Promise<WeeklyReviewResponse> {
  const q = date ? `?date=${date}` : "";
  return fetchJSON<WeeklyReviewResponse>(`/weekly-review${q}`);
}

export function askQuestion(req: AskRequest): Promise<AskResponse> {
  return postJSON<AskResponse>("/ask", req);
}
