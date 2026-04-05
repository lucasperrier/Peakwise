/** TypeScript types aligned with backend API schemas. */

// ---------------------------------------------------------------------------
// Shared
// ---------------------------------------------------------------------------

export interface ScoresPayload {
  recovery: number | null;
  race_readiness: number | null;
  general_health: number | null;
  load_balance: number | null;
}

// ---------------------------------------------------------------------------
// GET /api/today
// ---------------------------------------------------------------------------

export interface RecommendationPayload {
  mode: string;
  recommended_action: string;
  intensity_modifier: string | null;
  duration_modifier: string | null;
  reason_codes: string[];
  next_best_alternative: string | null;
  risk_flags: string[];
}

export interface TodayResponse {
  date: string;
  recommendation: RecommendationPayload | null;
  scores: ScoresPayload | null;
  subcomponents: Record<string, Record<string, number | null>> | null;
  warnings: Record<string, boolean> | null;
  explanation: string | null;
  confidence_score: number | null;
  confidence_level: string | null;
  score_version: string | null;
  recommendation_version: string | null;
}

// ---------------------------------------------------------------------------
// GET /api/running
// ---------------------------------------------------------------------------

export interface RunningFeatures {
  weekly_km: number | null;
  rolling_4w_km: number | null;
  longest_run_last_7d_km: number | null;
  easy_pace_fixed_hr_sec_per_km: number | null;
  quality_sessions_last_14d: number | null;
  projected_hm_time_sec: number | null;
  plan_adherence_pct: number | null;
}

export interface RunningTrendPoint {
  date: string;
  weekly_km: number | null;
  rolling_4w_km: number | null;
  longest_run_last_7d_km: number | null;
  easy_pace_fixed_hr_sec_per_km: number | null;
  quality_sessions_last_14d: number | null;
}

export interface RunningResponse {
  date: string;
  current: RunningFeatures | null;
  race_readiness_score: number | null;
  trend: RunningTrendPoint[];
}

// ---------------------------------------------------------------------------
// GET /api/health
// ---------------------------------------------------------------------------

export interface HealthFeatures {
  body_weight_7d_avg: number | null;
  body_weight_28d_slope: number | null;
  sleep_consistency_score: number | null;
  hrv_7d_avg: number | null;
  resting_hr_7d_avg: number | null;
  sleep_7d_avg: number | null;
  sleep_debt_min: number | null;
  mood_trend: number | null;
  stress_trend: number | null;
  steps_consistency_score: number | null;
  pain_free_days_last_14d: number | null;
}

export interface HealthTrendPoint {
  date: string;
  body_weight_7d_avg: number | null;
  hrv_7d_avg: number | null;
  resting_hr_7d_avg: number | null;
  sleep_7d_avg: number | null;
  sleep_debt_min: number | null;
  mood_trend: number | null;
  stress_trend: number | null;
}

export interface HealthResponse {
  date: string;
  current: HealthFeatures | null;
  general_health_score: number | null;
  trend: HealthTrendPoint[];
}

// ---------------------------------------------------------------------------
// GET /api/strength
// ---------------------------------------------------------------------------

export interface StrengthFeatures {
  hard_day_count_7d: number | null;
  lower_body_crossfit_density_7d: number | null;
  long_run_protection_score: number | null;
  interference_risk_score: number | null;
  run_intensity_distribution: Record<string, number> | null;
}

export interface RecentWorkout {
  workout_id: string;
  session_date: string;
  session_type: string;
  duration_min: number | null;
  training_load: number | null;
  is_lower_body_dominant: boolean | null;
  raw_notes: string | null;
}

export interface StrengthTrendPoint {
  date: string;
  hard_day_count_7d: number | null;
  lower_body_crossfit_density_7d: number | null;
  interference_risk_score: number | null;
}

export interface StrengthResponse {
  date: string;
  current: StrengthFeatures | null;
  load_balance_score: number | null;
  recent_workouts: RecentWorkout[];
  trend: StrengthTrendPoint[];
}

// ---------------------------------------------------------------------------
// GET /api/weekly-review
// ---------------------------------------------------------------------------

export interface WeekSummary {
  start_date: string;
  end_date: string;
  avg_recovery_score: number | null;
  avg_race_readiness_score: number | null;
  avg_general_health_score: number | null;
  avg_load_balance_score: number | null;
  total_km: number | null;
  workout_count: number;
  avg_sleep_duration_min: number | null;
  avg_hrv_ms: number | null;
  avg_resting_hr_bpm: number | null;
}

export interface ScoreChange {
  previous: number | null;
  current: number | null;
  delta: number | null;
}

export interface ScoreChanges {
  recovery: ScoreChange | null;
  race_readiness: ScoreChange | null;
  general_health: ScoreChange | null;
  load_balance: ScoreChange | null;
}

export interface WeeklyReviewResponse {
  current_week: WeekSummary;
  previous_week: WeekSummary | null;
  score_changes: ScoreChanges | null;
  flags: string[];
  explanation: string | null;
}

// ---------------------------------------------------------------------------
// POST /api/ask
// ---------------------------------------------------------------------------

export interface AskRequest {
  question: string;
  date?: string;
}

export interface AskResponse {
  answer: string | null;
  error: string | null;
}

// ---------------------------------------------------------------------------
// POST /api/feedback
// ---------------------------------------------------------------------------

export interface FeedbackRequest {
  date: string;
  rating: "accurate" | "too_hard" | "too_easy" | "pain_increased" | "ignored";
  free_text_note?: string;
  actual_session_type?: string;
  next_day_outcome?: string;
}

export interface FeedbackResponse {
  id: number;
  date: string;
  rating: string;
  created: boolean;
}

// ---------------------------------------------------------------------------
// GET /api/debug/day
// ---------------------------------------------------------------------------

export interface DebugDayResponse {
  date: string;
  daily_facts: Record<string, unknown> | null;
  features: Record<string, unknown> | null;
  workouts_in_lookback: Record<string, unknown>[];
  baselines: Record<string, number | null>;
  score_snapshot: Record<string, unknown> | null;
  score_components: Array<{
    score_type: string;
    component_name: string;
    raw_input_value: number | null;
    normalized_value: number | null;
    weighted_contribution: number | null;
    direction: string;
  }>;
  reason_codes: Array<{
    code: string;
    source: string;
    severity: string | null;
    detail: string | null;
  }>;
  recommendation: Record<string, unknown> | null;
  confidence: { score: number; level: string };
  source_coverage: Record<string, boolean>;
  field_provenance: Record<string, string | null>;
  score_breakdown: Record<string, unknown> | null;
}
