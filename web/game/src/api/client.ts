export type Suspect = { id: string; name: string }

export type GameState = {
  session_id: string
  case_id?: string
  title?: string
  suspects: Suspect[]
  evidence_ids: string[]
  pressure: Record<string, number>
  break_count: Record<string, number>
  mental_break_suspects: string[]
  timeout_strikes: number
  timeout_strike_max: number
  stamina: number
  stamina_max: number
  status: string
  turn_seconds: number
  timer_enabled: boolean
  ended: boolean
  accused?: boolean
  turn?: number
}

export type CaseOverview = {
  case_id: string
  title?: string
  synopsis?: string
  discovered_at?: string
  location?: string
  incident?: string
  player_role?: string
  objective?: string
  notes?: string
}

export type SuspectProfile = {
  id: string
  name: string
  mbti?: string
  traits?: string[]
  profile?: Record<string, string>
}

export type Clue = {
  evidence_id?: string
  title?: string
  body?: string
  flavor?: string
  snippet?: string
  smoking_gun?: boolean
}

function apiBase(): string {
  const q = new URLSearchParams(window.location.search)
  const fromQ = q.get('api')
  if (fromQ) return fromQ.replace(/\/$/, '')
  // vite dev uses proxy; prod nginx same-origin /api
  return ''
}

async function req<T>(path: string, init?: RequestInit): Promise<T> {
  const res = await fetch(`${apiBase()}${path}`, {
    headers: { 'Content-Type': 'application/json', ...(init?.headers || {}) },
    ...init,
  })
  // body는 한 번만 읽음 (json 실패 후 text 재읽기 → stream already read 방지)
  const raw = await res.text()
  let data: unknown = null
  if (raw) {
    try {
      data = JSON.parse(raw)
    } catch {
      data = null
    }
  }
  if (!res.ok) {
    const detail =
      data && typeof data === 'object' && data !== null && 'detail' in data
        ? String((data as { detail?: unknown }).detail || '')
        : ''
    if (detail) throw new Error(detail)
    if (res.status === 502 || res.status === 503 || res.status === 504) {
      throw new Error(
        `API 서버(127.0.0.1:8000)에 연결할 수 없습니다 (HTTP ${res.status}). uvicorn이 켜져 있는지 확인하세요.`,
      )
    }
    throw new Error(raw.slice(0, 200) || `HTTP ${res.status}`)
  }
  if (data === null && raw) {
    throw new Error('Invalid JSON response')
  }
  return data as T
}

export const api = {
  createSession: () => req<GameState>('/api/v1/session', { method: 'POST' }),
  getSession: (sid: string) => req<GameState>(`/api/v1/session/${sid}`),
  getCase: (sid: string) => req<CaseOverview>(`/api/v1/session/${sid}/case`),
  getProfile: (sid: string, suspectId: string) =>
    req<SuspectProfile>(`/api/v1/session/${sid}/suspects/${suspectId}/profile`),
  ask: (sid: string, body: { suspect_id: string; question: string }) =>
    req<{
      answer?: string
      assistant_note?: string
      is_alibi_broken?: boolean
      break_count?: number
      state: GameState
      agent_transcript?: unknown[]
      autogen?: Record<string, unknown>
      gm_status?: string
      reply_source?: string
      llm_notice?: string | null
    }>(`/api/v1/session/${sid}/ask`, { method: 'POST', body: JSON.stringify(body) }),
  observabilityStatus: () =>
    req<{
      enabled: boolean
      langfuse_configured: boolean
      langfuse_host?: string | null
      note?: string
    }>('/api/v1/observability/status'),
  getObservability: (sid: string, limit = 12) =>
    req<{
      enabled: boolean
      langfuse_configured: boolean
      langfuse_host?: string | null
      langfuse_traces_url?: string | null
      langfuse_sessions_url?: string | null
      langfuse_session_url?: string | null
      source: string
      remote_error?: string | null
      count: number
      trace_count?: number
      session_count?: number
      traces: Array<{
        id: string
        ts?: string
        session_id?: string
        name?: string
        suspect_name?: string
        suspect_id?: string
        question?: string
        answer?: string
        assistant_note?: string
        reply_source?: string
        model?: string
        gm_status?: string
        elapsed_sec?: number | null
        roles?: string[]
        langfuse_synced?: boolean
        langfuse_url?: string | null
      }>
      session_traces?: Array<{
        id: string
        ts?: string
        session_id?: string
        name?: string
        suspect_name?: string
        suspect_id?: string
        question?: string
        answer?: string
        assistant_note?: string
        reply_source?: string
        model?: string
        gm_status?: string
        elapsed_sec?: number | null
        roles?: string[]
        langfuse_synced?: boolean
        langfuse_url?: string | null
      }>
      sessions?: Array<{
        id: string
        created_at?: string | null
        environment?: string
        trace_count?: number | null
        current?: boolean
        langfuse_url?: string | null
      }>
    }>(`/api/v1/session/${sid}/observability?limit=${limit}`),
  getObservabilitySession: (obsSessionId: string, limit = 12) =>
    req<{
      session_id: string
      source: string
      remote_error?: string | null
      count: number
      traces: Array<{
        id: string
        ts?: string
        session_id?: string
        name?: string
        suspect_name?: string
        suspect_id?: string
        question?: string
        answer?: string
        assistant_note?: string
        reply_source?: string
        model?: string
        gm_status?: string
        elapsed_sec?: number | null
        roles?: string[]
        langfuse_synced?: boolean
        langfuse_url?: string | null
      }>
    }>(`/api/v1/observability/sessions/${encodeURIComponent(obsSessionId)}?limit=${limit}`),
  search: (
    sid: string,
    body: { query: string; force_miss?: boolean; force_evidence_id?: string | null },
  ) =>
    req<{
      hits?: unknown[]
      new_clues?: Clue[]
      useless_search?: boolean
      already_owned?: boolean
      authority_revoked?: boolean
      ending?: string
      stamina?: number
      stamina_max?: number
      state: GameState
    }>(`/api/v1/session/${sid}/search`, { method: 'POST', body: JSON.stringify(body) }),
  accuse: (sid: string, body: { suspect_id: string; evidence_ids: string[] }) =>
    req<{
      correct?: boolean
      ending?: string
      authority_revoked?: boolean
      state: GameState
    }>(`/api/v1/session/${sid}/accuse`, { method: 'POST', body: JSON.stringify(body) }),
}

export function assetUrl(rel: string): string {
  const q = new URLSearchParams(window.location.search)
  const base = (q.get('assets') || '/assets').replace(/\/$/, '')
  return `${base}/${rel.replace(/^\//, '')}`
}
