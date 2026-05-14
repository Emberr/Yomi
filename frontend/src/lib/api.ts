/**
 * CSRF-aware API client.
 *
 * Security contract:
 * - CSRF token is cached in module-level memory only — never written to
 *   localStorage, sessionStorage, or any persistent browser storage.
 * - Session cookie is httpOnly and managed entirely by the browser.
 * - All fetches use credentials: 'include' so the session cookie is sent.
 * - Every mutating method (POST/PUT/PATCH/DELETE) attaches X-CSRF-Token.
 */

const API_BASE = process.env.NEXT_PUBLIC_API_BASE ?? "/api";

// ── CSRF ────────────────────────────────────────────────────────────────────

/** In-memory only. Cleared on logout or explicit invalidation. */
let _csrfToken: string | null = null;

async function ensureCsrf(): Promise<string> {
  if (_csrfToken !== null) return _csrfToken;
  const res = await fetch(`${API_BASE}/auth/csrf-token`, {
    credentials: "include",
  });
  if (!res.ok) throw new Error("Failed to obtain CSRF token");
  const json = (await res.json()) as { data: { csrf_token: string } };
  _csrfToken = json.data.csrf_token;
  return _csrfToken;
}

export function invalidateCsrf(): void {
  _csrfToken = null;
}

// ── Core fetch ───────────────────────────────────────────────────────────────

const MUTATING = new Set(["POST", "PUT", "PATCH", "DELETE"]);

async function apiFetch(path: string, init?: RequestInit): Promise<Response> {
  const method = (init?.method ?? "GET").toUpperCase();
  const headers = new Headers(init?.headers);
  headers.set("Accept", "application/json");
  if (init?.body !== undefined) {
    headers.set("Content-Type", "application/json");
  }
  if (MUTATING.has(method)) {
    headers.set("X-CSRF-Token", await ensureCsrf());
  }
  return fetch(`${API_BASE}${path}`, {
    ...init,
    headers,
    credentials: "include",
  });
}

// ── Types ────────────────────────────────────────────────────────────────────

export interface UserInfo {
  id: number;
  username: string;
  display_name: string;
  is_admin: boolean;
}

export interface ApiOk<T> {
  ok: true;
  data: T;
}

export interface ApiErr {
  ok: false;
  error: string;
}

export type ApiResult<T> = ApiOk<T> | ApiErr;

function extractError(json: unknown): string {
  if (typeof json !== "object" || json === null) return "Unexpected error";
  const obj = json as Record<string, unknown>;
  const detail = obj["detail"];
  if (typeof detail === "string") return detail;
  if (Array.isArray(detail) && detail.length > 0) {
    const first = detail[0];
    if (typeof first === "object" && first !== null && "msg" in first) {
      return String((first as Record<string, unknown>)["msg"]);
    }
  }
  return "Unexpected error";
}

// ── Auth API calls ────────────────────────────────────────────────────────────

export async function apiGetMe(): Promise<UserInfo | null> {
  const res = await apiFetch("/auth/me");
  if (res.status === 401) return null;
  const json = (await res.json()) as { data: { user: UserInfo } };
  return json.data.user;
}

export async function apiLogin(
  username: string,
  password: string,
): Promise<ApiResult<UserInfo>> {
  const res = await apiFetch("/auth/login", {
    method: "POST",
    body: JSON.stringify({ username, password }),
  });
  const json: unknown = await res.json();
  if (!res.ok) return { ok: false, error: extractError(json) };
  return { ok: true, data: (json as { data: { user: UserInfo } }).data.user };
}

export async function apiLogout(): Promise<void> {
  await apiFetch("/auth/logout", { method: "POST" });
  invalidateCsrf();
}

export async function apiRegister(payload: {
  invite_code: string;
  username: string;
  display_name: string;
  password: string;
}): Promise<ApiResult<UserInfo>> {
  const res = await apiFetch("/auth/register", {
    method: "POST",
    body: JSON.stringify(payload),
  });
  const json: unknown = await res.json();
  if (!res.ok) return { ok: false, error: extractError(json) };
  return { ok: true, data: (json as { data: { user: UserInfo } }).data.user };
}

export async function apiChangePassword(
  current_password: string,
  new_password: string,
): Promise<ApiResult<null>> {
  const res = await apiFetch("/auth/change-password", {
    method: "POST",
    body: JSON.stringify({ current_password, new_password }),
  });
  const json: unknown = await res.json();
  if (!res.ok) return { ok: false, error: extractError(json) };
  return { ok: true, data: null };
}

// ── Grammar types ─────────────────────────────────────────────────────────────

export interface GrammarSummary {
  id: number;
  slug: string;
  title: string;
  jlpt_level: string;
  short_desc: string;
}

export interface GrammarDetail {
  id: number;
  slug: string;
  title: string;
  jlpt_level: string;
  jlpt_source: string;
  short_desc: string;
  long_desc: string;
  formation_pattern: string;
  common_mistakes: string | null;
  tags: string[];
  sort_order: number;
  source_file: string;
}

export interface ExampleSentence {
  id: number;
  grammar_id: number;
  japanese: string;
  reading: string;
  translation: string;
  audio_url: string | null;
  tags: string[];
}

// ── Vocab types ───────────────────────────────────────────────────────────────

export interface VocabSummary {
  id: number;
  jmdict_id: string;
  slug: string;
  jlpt_level: string | null;
  kanji_forms: string[];
  reading_forms: string[];
  meanings: string[];
}

export interface VocabDetail {
  id: number;
  jmdict_id: string;
  slug: string;
  jlpt_level: string | null;
  jlpt_source: string | null;
  kanji_forms: string[];
  reading_forms: string[];
  meanings: string[];
  pos_tags: string[];
  frequency: number | null;
}

// ── SRS types ─────────────────────────────────────────────────────────────────

export interface CardSentence {
  japanese: string;
  reading: string;
  translation: string;
}

export interface SrsCard {
  id: number;
  user_id: number;
  card_type: string;
  content_id: number;
  content_table: string;
  state: string;
  due: string;
  display_prompt: string | null;
  display_answer: string | null;
  display_formation: string | null;
  display_sentences: CardSentence[] | null;
  display_readings: string[] | null;
}

export interface ReviewResult {
  card_id: number;
  state: string;
  due: string;
  stability: number | null;
  difficulty: number | null;
}

// ── Grammar API calls ─────────────────────────────────────────────────────────

export async function apiListGrammar(
  level?: string,
): Promise<ApiResult<GrammarSummary[]>> {
  const qs = level ? `?level=${encodeURIComponent(level)}` : "";
  const res = await apiFetch(`/grammar${qs}`);
  const json: unknown = await res.json();
  if (!res.ok) return { ok: false, error: extractError(json) };
  return {
    ok: true,
    data: (json as { data: GrammarSummary[] }).data,
  };
}

export async function apiGetGrammar(
  slug: string,
): Promise<ApiResult<GrammarDetail>> {
  const res = await apiFetch(`/grammar/${encodeURIComponent(slug)}`);
  const json: unknown = await res.json();
  if (!res.ok) return { ok: false, error: extractError(json) };
  return { ok: true, data: (json as { data: GrammarDetail }).data };
}

export async function apiGetGrammarSentences(
  slug: string,
): Promise<ApiResult<ExampleSentence[]>> {
  const res = await apiFetch(
    `/grammar/${encodeURIComponent(slug)}/sentences`,
  );
  const json: unknown = await res.json();
  if (!res.ok) return { ok: false, error: extractError(json) };
  return { ok: true, data: (json as { data: ExampleSentence[] }).data };
}

// ── Vocab API calls ───────────────────────────────────────────────────────────

export async function apiSearchVocab(
  q: string,
  opts?: { level?: string; limit?: number },
): Promise<ApiResult<VocabSummary[]>> {
  const params = new URLSearchParams({ q });
  if (opts?.level) params.set("level", opts.level);
  if (opts?.limit !== undefined) params.set("limit", String(opts.limit));
  const res = await apiFetch(`/vocab/search?${params.toString()}`);
  const json: unknown = await res.json();
  if (!res.ok) return { ok: false, error: extractError(json) };
  return { ok: true, data: (json as { data: VocabSummary[] }).data };
}

export async function apiGetVocab(id: number): Promise<ApiResult<VocabDetail>> {
  const res = await apiFetch(`/vocab/${id}`);
  const json: unknown = await res.json();
  if (!res.ok) return { ok: false, error: extractError(json) };
  return { ok: true, data: (json as { data: VocabDetail }).data };
}

// ── SRS API calls ─────────────────────────────────────────────────────────────

export async function apiCreateSrsCard(payload: {
  content_id: number;
  content_table: string;
  card_type: string;
}): Promise<ApiResult<SrsCard>> {
  const res = await apiFetch("/srs/cards", {
    method: "POST",
    body: JSON.stringify(payload),
  });
  const json: unknown = await res.json();
  if (!res.ok) return { ok: false, error: extractError(json) };
  return { ok: true, data: (json as { data: SrsCard }).data };
}

export async function apiGetDueCards(): Promise<ApiResult<SrsCard[]>> {
  const res = await apiFetch("/srs/due");
  const json: unknown = await res.json();
  if (!res.ok) return { ok: false, error: extractError(json) };
  return { ok: true, data: (json as { data: SrsCard[] }).data };
}

export async function apiSubmitReview(payload: {
  card_id: number;
  rating: 1 | 2 | 3 | 4;
  time_taken_ms?: number;
}): Promise<ApiResult<ReviewResult>> {
  const res = await apiFetch("/srs/review", {
    method: "POST",
    body: JSON.stringify(payload),
  });
  const json: unknown = await res.json();
  if (!res.ok) return { ok: false, error: extractError(json) };
  return { ok: true, data: (json as { data: ReviewResult }).data };
}
