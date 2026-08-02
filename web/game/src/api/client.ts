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
  if (!res.ok) {
    let detail = ''
    try {
      const j = await res.json()
      detail = String(j?.detail || '')
    } catch {
      detail = (await res.text()).slice(0, 200)
    }
    throw new Error(detail || `HTTP ${res.status}`)
  }
  return res.json() as Promise<T>
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
    }>(`/api/v1/session/${sid}/ask`, { method: 'POST', body: JSON.stringify(body) }),
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
