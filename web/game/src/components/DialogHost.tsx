import { useMemo, useState } from 'react'
import { api, assetUrl } from '../api/client'
import { CLUE_FLAVOR, CLUE_LABELS } from '../data/deskItems'
import { GOLDEN_ROUTE_STEPS } from '../data/goldenRoute'
import { useGameStore, type ObsPayload, type ObsTrace } from '../state/gameStore'
import { Modal } from './Modal'

const PROFILE_IDENTITY: [string, string][] = [
  ['archetype', '유형'],
  ['age_group', '나이대'],
  ['rank', '직급'],
  ['personality', '성격'],
  ['gender', '성별'],
  ['birth_date', '생년월일'],
  ['height', '키'],
  ['weight', '몸무게'],
  ['eye_color', '눈 색'],
  ['hair_color', '머리 색'],
  ['occupation', '직업'],
  ['marital_status', '결혼유무'],
  ['family', '가족관계'],
  ['criminal_record', '범죄이력'],
  ['notes', '특이사항'],
]

const PROFILE_INTERROGATION: [string, string][] = [
  ['speech_style', '말투'],
  ['fluster_reaction', '당황 시 반응'],
  ['sample_line', '예시 대사'],
  ['claimed_alibi', '주장 알리바이'],
]

export function DialogHost() {
  const modal = useGameStore((s) => s.modal)
  const caseInfo = useGameStore((s) => s.caseInfo)
  const dossier = useGameStore((s) => s.dossier)
  const deskAlert = useGameStore((s) => s.deskAlert)
  const pendingClues = useGameStore((s) => s.pendingClues)
  const accuseFlash = useGameStore((s) => s.accuseFlash)
  const revokedMsg = useGameStore((s) => s.revokedMsg)
  const startGame = useGameStore((s) => s.startGame)
  const closeModal = useGameStore((s) => s.closeModal)
  const confirmClue = useGameStore((s) => s.confirmClue)
  const ackAccuse = useGameStore((s) => s.ackAccuse)
  const ackRevoked = useGameStore((s) => s.ackRevoked)
  const evidenceReadyMsg = useGameStore((s) => s.evidenceReadyMsg)
  const setTab = useGameStore((s) => s.setTab)
  const observability = useGameStore((s) => s.observability)
  const obsLoading = useGameStore((s) => s.obsLoading)
  const openObservability = useGameStore((s) => s.openObservability)
  const game = useGameStore((s) => s.game)

  if (modal === 'briefing') {
    return (
      <Modal title="수사 브리핑" dismissible={false} wide>
        <CaseBody layout="briefing" />
        <p className="briefing-foot">
          브리핑 확인 후 START · 조작법은 「HOW TO · 게임 방법」에서 볼 수 있습니다.
        </p>
        <div className="briefing-actions">
          <button type="button" className="primary-btn modal-action" onClick={() => startGame()}>
            START
          </button>
        </div>
      </Modal>
    )
  }

  if (modal === 'case') {
    return (
      <Modal title="사건개요" onClose={closeModal} wide>
        <CaseBody layout="briefing" />
        <div className="briefing-actions">
          <button type="button" className="primary-btn modal-action" onClick={closeModal}>
            확인
          </button>
        </div>
      </Modal>
    )
  }

  if (modal === 'howto') {
    return (
      <Modal title="게임 방법" onClose={closeModal} wide>
        <HowtoBody />
        <div className="briefing-actions">
          <button type="button" className="primary-btn modal-action" onClick={closeModal}>
            확인
          </button>
        </div>
      </Modal>
    )
  }

  if (modal === 'dossier' && dossier) {
    const profile = dossier.profile || {}
    const traitLine = dossier.traits?.length ? dossier.traits.join(' · ') : '—'
    const identityRows = buildProfileRows(dossier.name, profile, PROFILE_IDENTITY, {
      includeName: true,
      includeUnknown: true,
    })
    const interrogRows = buildProfileRows(dossier.name, profile, PROFILE_INTERROGATION, {
      includeName: false,
      includeUnknown: false,
    })
    return (
      <Modal title="수사 파일" onClose={closeModal} wide>
        <div className="dossier-shell">
          <div className="briefing-panel dossier-panel">
            <p className="modal-kicker">
              CHARACTER PROFILE · CASE {caseInfo?.case_id || 'case_01'}
            </p>
            <div className="dossier-grid">
              <div className="dossier-fullbody">
                <img
                  src={assetUrl(`suspects/${dossier.id}_full.webp`)}
                  alt={`${dossier.name} 전신`}
                  onError={(e) => {
                    const img = e.currentTarget
                    if (img.src.endsWith('.webp')) {
                      img.src = assetUrl(`suspects/${dossier.id}_full.jpg`)
                    } else if (img.src.endsWith('.jpg')) {
                      img.src = assetUrl(`suspects/${dossier.id}_full.png`)
                    }
                  }}
                />
              </div>
              <div className="dossier-info">
                <h3 className="dossier-name">{dossier.name}</h3>
                <p className="dossier-meta">
                  MBTI {dossier.mbti || '—'} · {traitLine}
                </p>
                <ProfileRows rows={identityRows} variant="grid" />
              </div>
            </div>
          </div>
          {interrogRows.length ? (
            <div className="briefing-panel dossier-panel dossier-interrog-panel">
              <p className="modal-kicker">INTERROGATION NOTE</p>
              <p className="dossier-interrog-lead">말투 · 당황 반응 · 예시 대사 · 주장 알리바이</p>
              <ProfileRows rows={interrogRows} variant="stack" />
            </div>
          ) : null}
        </div>
        <div className="briefing-actions">
          <button type="button" className="primary-btn modal-action" onClick={closeModal}>
            확인
          </button>
        </div>
      </Modal>
    )
  }

  if (modal === 'desk_alert' && deskAlert) {
    return (
      <Modal title={deskAlert.title || '수색 결과'} dismissible={false} alert>
        {deskAlert.kind === 'warn' ? (
          <div className="alert-banner is-warn">{deskAlert.text}</div>
        ) : deskAlert.kind === 'error' ? (
          <div className="alert-banner is-error">{deskAlert.text}</div>
        ) : deskAlert.kind === 'ok' ? (
          <div className="alert-banner is-ok">{deskAlert.text}</div>
        ) : (
          <div className="alert-banner is-info">{deskAlert.text}</div>
        )}
        {deskAlert.kind === 'warn' ? (
          <p className="modal-caption">헛수색 1회마다 수사 권한이 1 감소합니다.</p>
        ) : null}
        <button type="button" className="primary-btn modal-action" onClick={closeModal}>
          확인
        </button>
      </Modal>
    )
  }

  if (modal === 'evidence_ready' && evidenceReadyMsg) {
    return (
      <Modal title="증거 확보 완료" dismissible={false} alert>
        <div className="alert-banner is-ok evidence-ready-banner">
          {evidenceReadyMsg.split('\n').map((line, i) => (
            <p key={i} className={i === 0 ? 'evidence-ready-lead' : 'evidence-ready-sub'}>
              {line || '\u00a0'}
            </p>
          ))}
        </div>
        <div className="briefing-actions evidence-ready-actions">
          <button
            type="button"
            className="primary-btn modal-action"
            onClick={() => {
              setTab('accuse')
              closeModal()
            }}
          >
            최종 지목으로
          </button>
          <button type="button" className="ghost-btn modal-action" onClick={closeModal}>
            계속 수사
          </button>
        </div>
      </Modal>
    )
  }

  if (modal === 'desk_clue' && pendingClues[0]) {
    const clue = pendingClues[0]
    const eid = String(clue.evidence_id || '')
    const title = clue.title || CLUE_LABELS[eid] || eid
    const flavor = clue.body || clue.flavor || CLUE_FLAVOR[eid] || '결정적 단서가 확보되었습니다.'
    const snip = String(clue.snippet || '').trim()
    const showSnip = snip && snip !== title && snip !== flavor && snip.length <= 120
    const goldenMeta = GOLDEN_ROUTE_STEPS.findIndex((s) => s.evidence_id === eid)
    const smoking = Boolean(clue.smoking_gun) || goldenMeta >= 0
    let kicker = 'Evidence Secured'
    let routeLine = ''
    if (goldenMeta >= 0) {
      const step = GOLDEN_ROUTE_STEPS[goldenMeta]
      kicker = step.kicker
      routeLine = `Golden Route ${goldenMeta + 1}/${GOLDEN_ROUTE_STEPS.length} · ${step.beat}`
    } else if (smoking) {
      kicker = 'Smoking Gun'
    }
    return (
      <Modal title="수색 결과" dismissible={false} alert>
        <div className={`clue-banner${smoking ? ' is-smoking' : ''}`}>
          <div className="clue-kicker">{kicker}</div>
          <div className="clue-title">{title}</div>
          <p className="clue-snip">{flavor}</p>
          {showSnip ? <p className="clue-snip" style={{ marginTop: '0.3rem' }}>{snip}</p> : null}
          {routeLine ? <p className="clue-route">{routeLine}</p> : null}
        </div>
        <p className="modal-caption">
          인벤토리는 왼쪽 사이드바(☰)에서 확인할 수 있습니다.
        </p>
        <button type="button" className="primary-btn modal-action" onClick={confirmClue}>
          단서 확인 · 인벤토리에 보관
        </button>
      </Modal>
    )
  }

  if (modal === 'accuse' && accuseFlash) {
    return (
      <Modal title="지목 결과" dismissible={false} alert>
        <div
          className={`ending-banner${accuseFlash.won ? ' is-win' : ' is-lose'}`}
        >
          <div className="ending-kicker">
            {accuseFlash.won
              ? 'CASE CLOSED · GOLDEN ROUTE'
              : accuseFlash.revoked
                ? 'AUTHORITY REVOKED'
                : 'JUDGEMENT FAILED'}
          </div>
          <div className="ending-title">
            {accuseFlash.won
              ? '진실이 밝혀졌습니다'
              : accuseFlash.revoked
                ? '수사 권한이 박탈되었습니다'
                : '지목이 빗나갔습니다'}
          </div>
          <p>{accuseFlash.text}</p>
        </div>
        {!accuseFlash.won && !accuseFlash.revoked ? (
          <p className="modal-caption">
            오답 지목 1회마다 수사 권한이 1 감소합니다. 조합을 다시 검토하세요.
          </p>
        ) : null}
        <button type="button" className="primary-btn modal-action" onClick={ackAccuse}>
          확인
        </button>
      </Modal>
    )
  }

  if (modal === 'revoked') {
    return (
      <Modal title="수사 권한 박탈" dismissible={false} alert>
        <div className="ending-banner is-lose">
          <div className="ending-kicker">AUTHORITY REVOKED</div>
          <div className="ending-title">수사 권한이 박탈되었습니다</div>
          <p>
            {revokedMsg ||
              '감사관, 당신은 무능합니다. 수사 권한이 박탈되었습니다.'}
          </p>
        </div>
        <button type="button" className="primary-btn modal-action" onClick={ackRevoked}>
          확인
        </button>
      </Modal>
    )
  }

  if (modal === 'observability') {
    return (
      <ObservabilityModal
        observability={observability}
        obsLoading={obsLoading}
        sessionId={game?.session_id || ''}
        onRefresh={() => void openObservability()}
        onClose={closeModal}
      />
    )
  }

  return null
}

function ObservabilityModal({
  observability,
  obsLoading,
  sessionId,
  onRefresh,
  onClose,
}: {
  observability: ObsPayload | null
  obsLoading: boolean
  sessionId: string
  onRefresh: () => void
  onClose: () => void
}) {
  const [tab, setTab] = useState<'tracing' | 'sessions'>('tracing')
  const projectTraces = observability?.traces || []
  const sessionTraces = observability?.session_traces || []
  const sessions = observability?.sessions || []
  const openUrl =
    tab === 'tracing'
      ? observability?.langfuse_traces_url || observability?.langfuse_sessions_url
      : observability?.langfuse_sessions_url || observability?.langfuse_session_url

  return (
    <div className="obs-board" role="dialog" aria-modal="true" aria-label="Observability · Langfuse">
      <div className="obs-board-inner">
        <header className="obs-board-header">
          <div className="obs-board-heading">
            <p className="modal-kicker">FIELD OBSERVATORY</p>
            <h2 className="obs-board-title">Observability · Langfuse</h2>
            <p className="obs-session-id">
              {sessionId ? `Current session ${sessionId}` : 'Langfuse board'}
            </p>
          </div>
          <div className="obs-board-header-right">
            <div className="obs-session-stats">
              <span>
                Traces{' '}
                <strong>{obsLoading ? '…' : observability?.trace_count ?? projectTraces.length}</strong>
              </span>
              <span>
                Sessions{' '}
                <strong>{obsLoading ? '…' : observability?.session_count ?? sessions.length}</strong>
              </span>
              {observability?.langfuse_configured ? (
                <span className="obs-pill is-on">Langfuse linked</span>
              ) : (
                <span className="obs-pill">local only</span>
              )}
            </div>
            <button type="button" className="obs-board-close" aria-label="Close" onClick={onClose}>
              ×
            </button>
          </div>
        </header>

        <div className="obs-board-toolbar">
          <div className="tabs obs-tabs" role="tablist" aria-label="Observability views">
            <button
              type="button"
              role="tab"
              aria-selected={tab === 'tracing'}
              className={`tab${tab === 'tracing' ? ' active' : ''}`}
              onClick={() => setTab('tracing')}
            >
              Tracing
            </button>
            <button
              type="button"
              role="tab"
              aria-selected={tab === 'sessions'}
              className={`tab${tab === 'sessions' ? ' active' : ''}`}
              onClick={() => setTab('sessions')}
            >
              Sessions
            </button>
          </div>
          {openUrl ? (
            <a className="obs-link obs-link-top" href={openUrl} target="_blank" rel="noreferrer">
              Open in Langfuse ↗
            </a>
          ) : null}
        </div>

        <div className="obs-board-body">
          {observability?.remote_error ? (
            <p className="alert-banner is-warn">Langfuse 조회: {observability.remote_error}</p>
          ) : null}

          {obsLoading ? (
            <p className="hint-muted">불러오는 중…</p>
          ) : tab === 'tracing' ? (
            <TracingPane traces={projectTraces} />
          ) : (
            <SessionsPane
              sessions={sessions}
              sessionTraces={sessionTraces}
              projectTraces={projectTraces}
              sessionId={sessionId}
            />
          )}
        </div>

        <footer className="obs-actions">
          <button type="button" className="side-btn" onClick={onRefresh} disabled={obsLoading}>
            새로고침
          </button>
          <button type="button" className="primary-btn" onClick={onClose}>
            확인
          </button>
        </footer>
      </div>
    </div>
  )
}

function TracingPane({ traces }: { traces: ObsTrace[] }) {
  const [q, setQ] = useState('')
  const [name, setName] = useState('all')
  const [session, setSession] = useState('all')
  const [synced, setSynced] = useState<'all' | 'yes' | 'local'>('all')

  const nameOptions = useMemo(() => {
    const set = new Set<string>()
    for (const t of traces) set.add(t.name || 'interrogation-ask')
    return Array.from(set).sort()
  }, [traces])

  const sessionOptions = useMemo(() => {
    const set = new Set<string>()
    for (const t of traces) {
      if (t.session_id) set.add(t.session_id)
    }
    return Array.from(set).sort()
  }, [traces])

  const filtered = useMemo(() => {
    const needle = q.trim().toLowerCase()
    return traces.filter((t) => {
      const tName = t.name || 'interrogation-ask'
      if (name !== 'all' && tName !== name) return false
      if (session !== 'all' && (t.session_id || '') !== session) return false
      if (synced === 'yes' && !t.langfuse_synced) return false
      if (synced === 'local' && t.langfuse_synced) return false
      if (!needle) return true
      const hay = [
        tName,
        t.session_id,
        t.question,
        t.answer,
        t.suspect_name,
        t.suspect_id,
        t.reply_source,
        t.model,
        t.gm_status,
      ]
        .filter(Boolean)
        .join(' ')
        .toLowerCase()
      return hay.includes(needle)
    })
  }, [traces, q, name, session, synced])

  if (traces.length === 0) {
    return (
      <p className="hint-muted">
        아직 프로젝트 트레이스가 없습니다. 심문 질문을 한 뒤 새로고침하면 Input / Output이 여기에
        쌓입니다.
      </p>
    )
  }

  return (
    <div className="obs-pane">
      <div className="obs-filters" role="search" aria-label="Tracing filters">
        <input
          type="search"
          className="obs-filter-input"
          placeholder="검색 · question / answer / session…"
          value={q}
          onChange={(e) => setQ(e.target.value)}
        />
        <label className="obs-filter-field">
          <span>Name</span>
          <select value={name} onChange={(e) => setName(e.target.value)}>
            <option value="all">All ({traces.length})</option>
            {nameOptions.map((n) => (
              <option key={n} value={n}>
                {n}
              </option>
            ))}
          </select>
        </label>
        <label className="obs-filter-field">
          <span>Session</span>
          <select value={session} onChange={(e) => setSession(e.target.value)}>
            <option value="all">All</option>
            {sessionOptions.map((s) => (
              <option key={s} value={s}>
                {s}
              </option>
            ))}
          </select>
        </label>
        <label className="obs-filter-field">
          <span>Synced</span>
          <select
            value={synced}
            onChange={(e) => setSynced(e.target.value as 'all' | 'yes' | 'local')}
          >
            <option value="all">All</option>
            <option value="yes">Langfuse</option>
            <option value="local">local</option>
          </select>
        </label>
        <span className="obs-filter-count">
          {filtered.length} / {traces.length}
        </span>
      </div>

      {filtered.length === 0 ? (
        <p className="hint-muted">필터 조건에 맞는 트레이스가 없습니다.</p>
      ) : (
        <div className="obs-table-wrap">
          <table className="obs-table">
            <thead>
              <tr>
                <th>Start Time</th>
                <th>Name</th>
                <th>Input</th>
                <th>Output</th>
                <th>Session</th>
              </tr>
            </thead>
            <tbody>
              {filtered.map((t) => (
                <tr key={t.id}>
                  <td className="obs-td-time">{t.ts ? formatObsTime(t.ts) : '—'}</td>
                  <td>
                    <span className="obs-type">span</span>{' '}
                    <strong>{t.name || 'interrogation-ask'}</strong>
                  </td>
                  <td className="obs-td-io" title={t.question || ''}>
                    {t.question || '—'}
                  </td>
                  <td className="obs-td-io" title={t.answer || ''}>
                    {t.answer || '—'}
                  </td>
                  <td className="mono">{t.session_id || '—'}</td>
                </tr>
              ))}
            </tbody>
          </table>
        </div>
      )}
    </div>
  )
}

function SessionsPane({
  sessions,
  sessionTraces,
  projectTraces,
  sessionId,
}: {
  sessions: NonNullable<ObsPayload['sessions']>
  sessionTraces: ObsTrace[]
  projectTraces: ObsTrace[]
  sessionId: string
}) {
  const [openId, setOpenId] = useState<string | null>(null)
  const [cache, setCache] = useState<Record<string, ObsTrace[]>>(() => {
    const init: Record<string, ObsTrace[]> = {}
    if (sessionId && sessionTraces.length) init[sessionId] = sessionTraces
    return init
  })
  const [loadingId, setLoadingId] = useState<string | null>(null)
  const [errorById, setErrorById] = useState<Record<string, string>>({})
  const [q, setQ] = useState('')
  const [scope, setScope] = useState<'all' | 'current'>('all')
  const [env, setEnv] = useState('all')

  const envOptions = useMemo(() => {
    const set = new Set<string>()
    for (const s of sessions) {
      if (s.environment) set.add(s.environment)
    }
    return Array.from(set).sort()
  }, [sessions])

  const filtered = useMemo(() => {
    const needle = q.trim().toLowerCase()
    return sessions.filter((s) => {
      if (scope === 'current' && !s.current && s.id !== sessionId) return false
      if (env !== 'all' && (s.environment || 'default') !== env) return false
      if (!needle) return true
      const hay = [s.id, s.environment, s.created_at].filter(Boolean).join(' ').toLowerCase()
      return hay.includes(needle)
    })
  }, [sessions, q, scope, env, sessionId])

  const seedFor = (sid: string): ObsTrace[] => {
    if (cache[sid]?.length) return cache[sid]
    if (sid === sessionId && sessionTraces.length) return sessionTraces
    const fromProject = projectTraces.filter((t) => t.session_id === sid)
    return fromProject
  }

  const toggle = async (sid: string) => {
    if (openId === sid) {
      setOpenId(null)
      return
    }
    setOpenId(sid)
    if (cache[sid]?.length || (sid === sessionId && sessionTraces.length)) {
      if (!cache[sid]?.length && sessionTraces.length) {
        setCache((prev) => ({ ...prev, [sid]: sessionTraces }))
      }
      return
    }
    setLoadingId(sid)
    try {
      const data = await api.getObservabilitySession(sid, 12)
      setCache((prev) => ({ ...prev, [sid]: data.traces || [] }))
      setErrorById((prev) => {
        const next = { ...prev }
        delete next[sid]
        return next
      })
    } catch (e) {
      const seeded = seedFor(sid)
      if (seeded.length) {
        setCache((prev) => ({ ...prev, [sid]: seeded }))
      } else {
        setErrorById((prev) => ({
          ...prev,
          [sid]: e instanceof Error ? e.message : String(e),
        }))
      }
    } finally {
      setLoadingId(null)
    }
  }

  if (sessions.length === 0) {
    return <p className="hint-muted">세션 목록이 비어 있습니다.</p>
  }

  return (
    <div className="obs-sessions-pane">
      <div className="obs-filters" role="search" aria-label="Sessions filters">
        <input
          type="search"
          className="obs-filter-input"
          placeholder="검색 · session id…"
          value={q}
          onChange={(e) => setQ(e.target.value)}
        />
        <label className="obs-filter-field">
          <span>Scope</span>
          <select value={scope} onChange={(e) => setScope(e.target.value as 'all' | 'current')}>
            <option value="all">All sessions</option>
            <option value="current">Current only</option>
          </select>
        </label>
        {envOptions.length > 0 ? (
          <label className="obs-filter-field">
            <span>Environment</span>
            <select value={env} onChange={(e) => setEnv(e.target.value)}>
              <option value="all">All</option>
              {envOptions.map((e) => (
                <option key={e} value={e}>
                  {e}
                </option>
              ))}
            </select>
          </label>
        ) : null}
        <span className="obs-filter-count">
          {filtered.length} / {sessions.length}
        </span>
      </div>

      {filtered.length === 0 ? (
        <p className="hint-muted">필터 조건에 맞는 세션이 없습니다.</p>
      ) : (
        <ul className="obs-faq-list">
          {filtered.map((s) => {
            const expanded = openId === s.id
            const traces = cache[s.id] || seedFor(s.id)
            const loading = loadingId === s.id
            const err = errorById[s.id]
            return (
              <li
                key={s.id}
                className={`obs-faq-item${s.current ? ' is-current' : ''}${expanded ? ' is-open' : ''}`}
              >
                <button
                  type="button"
                  className="obs-faq-head"
                  aria-expanded={expanded}
                  onClick={() => void toggle(s.id)}
                >
                  <div className="obs-faq-head-main">
                    <strong className="mono">{s.id}</strong>
                    {s.current ? <span className="obs-pill is-on">current</span> : null}
                    <span className="obs-meta">
                      {s.created_at ? formatObsTime(s.created_at) : ''}
                      {s.environment ? ` · ${s.environment}` : ''}
                    </span>
                  </div>
                  <span className="obs-faq-toggle">{expanded ? '접기' : '펼치기'}</span>
                </button>
                {expanded ? (
                  <div className="obs-faq-body">
                    {loading ? <p className="hint-muted">트레이스 불러오는 중…</p> : null}
                    {!loading && err ? <p className="alert-banner is-warn">{err}</p> : null}
                    {!loading && !err && traces.length === 0 ? (
                      <p className="hint-muted">이 세션에 기록된 ask가 없습니다.</p>
                    ) : null}
                    {!loading && traces.length > 0 ? (
                      <ul className="obs-list">
                        {traces.map((t) => (
                          <ObsTraceCard key={t.id} t={t} />
                        ))}
                      </ul>
                    ) : null}
                  </div>
                ) : null}
              </li>
            )
          })}
        </ul>
      )}
    </div>
  )
}

function ObsTraceCard({ t }: { t: ObsTrace }) {
  const inputRows: [string, string][] = [
    ['question', t.question || '—'],
    ['suspect_id', t.suspect_id || '—'],
    ['suspect_name', t.suspect_name || '—'],
  ]
  const outputRows: [string, string][] = [
    ['answer', t.answer || '—'],
    ['assistant_note', t.assistant_note || '—'],
    ['gm_status', t.gm_status || '—'],
    ['reply_source', t.reply_source || '—'],
  ]
  return (
    <li className="obs-item">
      <div className="obs-item-title">
        <span className="obs-type">span</span>
        <strong>{t.name || 'interrogation-ask'}</strong>
        <span className="obs-meta">
          {t.elapsed_sec != null ? `${t.elapsed_sec}s` : ''}
          {t.ts ? ` · ${formatObsTime(t.ts)}` : ''}
        </span>
      </div>
      <div className="obs-grid">
        <div className="obs-main">
          <section className="obs-block">
            <h4>Input</h4>
            <div className="obs-kv">
              {inputRows.map(([k, v]) => (
                <div key={k} className="obs-kv-row">
                  <span className="obs-k">{k}</span>
                  <span className="obs-v">{v}</span>
                </div>
              ))}
            </div>
          </section>
          <section className="obs-block">
            <h4>Output</h4>
            <div className="obs-kv">
              {outputRows.map(([k, v]) => (
                <div key={k} className="obs-kv-row">
                  <span className="obs-k">{k}</span>
                  <span className="obs-v">{v}</span>
                </div>
              ))}
            </div>
          </section>
        </div>
        <aside className="obs-side">
          <h4>Metadata</h4>
          <div className="obs-kv obs-kv-compact">
            <div className="obs-kv-row">
              <span className="obs-k">id</span>
              <span className="obs-v mono">{t.id.slice(0, 12)}…</span>
            </div>
            <div className="obs-kv-row">
              <span className="obs-k">model</span>
              <span className="obs-v">{t.model || '—'}</span>
            </div>
            <div className="obs-kv-row">
              <span className="obs-k">roles</span>
              <span className="obs-v">{(t.roles || []).join(', ') || '—'}</span>
            </div>
            <div className="obs-kv-row">
              <span className="obs-k">synced</span>
              <span className="obs-v">{t.langfuse_synced ? 'yes' : 'local'}</span>
            </div>
          </div>
        </aside>
      </div>
    </li>
  )
}

function formatObsTime(ts: string): string {
  const d = new Date(ts)
  if (Number.isNaN(d.getTime())) return ts
  return d.toLocaleString('ko-KR', {
    month: 'numeric',
    day: 'numeric',
    hour: '2-digit',
    minute: '2-digit',
    second: '2-digit',
  })
}

function CaseBody({ layout = 'default' }: { layout?: 'default' | 'briefing' }) {
  const caseInfo = useGameStore((s) => s.caseInfo)
  if (!caseInfo) return <p>공개된 사건 정보가 없습니다.</p>
  const rows: [string, string][] = [
    ['발견·발생 시각', caseInfo.discovered_at || ''],
    ['장소', caseInfo.location || ''],
    ['사건', caseInfo.incident || ''],
    ['역할', caseInfo.player_role || ''],
    ['목표', caseInfo.objective || ''],
    ['기타', caseInfo.notes || caseInfo.synopsis || ''],
  ].filter(([, v]) => String(v).trim()) as [string, string][]

  if (layout === 'briefing') {
    const metaLabels = new Set(['발견·발생 시각', '장소', '역할'])
    const meta = rows.filter(([label]) => metaLabels.has(label))
    const details = rows.filter(([label]) => !metaLabels.has(label))
    return (
      <div className="briefing-body">
        <div className="briefing-panel">
          <p className="modal-kicker">CASE INFO · {(caseInfo.case_id || 'case_01').toUpperCase()}</p>
          <h3 className="briefing-case-title">{caseInfo.title || '사건개요'}</h3>
          {rows.length ? (
            <div className="briefing-facts">
              {meta.length ? (
                <div className="briefing-meta">
                  {meta.map(([label, value]) => (
                    <div key={label} className="briefing-fact">
                      <div className="briefing-fact-label">{label}</div>
                      <div className="briefing-fact-value">{value}</div>
                    </div>
                  ))}
                </div>
              ) : null}
              {details.map(([label, value]) => (
                <div key={label} className="briefing-fact briefing-fact-block">
                  <div className="briefing-fact-label">{label}</div>
                  <div className="briefing-fact-value">{value}</div>
                </div>
              ))}
            </div>
          ) : (
            <p className="briefing-empty">공개된 사건 정보가 없습니다.</p>
          )}
        </div>
      </div>
    )
  }

  return (
    <div>
      <p className="modal-kicker">CASE INFO · {caseInfo.case_id || 'case_01'}</p>
      <h2 className="case-info-title">{caseInfo.title || '사건개요'}</h2>
      {rows.length ? (
        <div className="dossier-rows case-info-rows">
          {rows.map(([label, value]) => (
            <div key={label} className="dossier-row">
              <div className="dossier-label">{label}</div>
              <div className="dossier-value">{value}</div>
            </div>
          ))}
        </div>
      ) : (
        <p style={{ color: 'var(--muted)' }}>공개된 사건 정보가 없습니다.</p>
      )}
    </div>
  )
}

function HowtoBody() {
  const steps = [
    [
      '01 용의자 선택',
      '「심문」·「최종 지목」 탭의 셀렉트 박스로 대상을 고릅니다. 초상은 현재 대상 표시용이며, 우측 하단 「프로필」은 조회용입니다.',
    ],
    [
      '02 심문',
      '「심문」 탭에서 질문을 입력하고 Enter로 전송합니다. 알리바이가 흔들리면 압박·붕괴 수치가 오릅니다.',
    ],
    [
      '03 증거 수색',
      '「증거 수색」 탭의 책상 보드에서 증거 후보를 골라 수색합니다. 헛수색 1회마다 수사 권한이 1 감소합니다.',
    ],
    [
      '04 최종 지목',
      '용의자 1명 + 인벤토리 증거 정확히 2장을 조합해 지목합니다. 오답이면 수사 권한이 감소합니다.',
    ],
    [
      '05 Golden Route',
      '사이드바 Golden Route는 데모용 정석 루트 힌트입니다. 법인카드 → 슬랙 → 네트워크 → 조합 지목 순을 따라가면 클리어에 가깝습니다.',
    ],
  ] as const
  return (
    <div className="briefing-body">
      <div className="briefing-panel">
        <p className="modal-kicker">HOW TO · FIELD MANUAL</p>
        <h3 className="briefing-case-title">수사 진행 방법</h3>
        <p className="briefing-lead">
          당신은 외부 디지털 포렌식 감사관입니다. <strong>심문 → 증거 수색 → 조합 지목</strong>{' '}
          순으로 진범을 밝히세요.
        </p>
        <div className="briefing-facts">
          {steps.map(([label, value]) => (
            <div key={label} className="briefing-fact briefing-fact-block">
              <div className="briefing-fact-label">{label}</div>
              <div className="briefing-fact-value">{value}</div>
            </div>
          ))}
        </div>
      </div>
    </div>
  )
}

function buildProfileRows(
  name: string,
  profile: Record<string, string>,
  fieldOrder: [string, string][],
  opts: { includeName: boolean; includeUnknown: boolean },
): [string, string][] {
  const rows: [string, string][] = []
  if (opts.includeName) rows.push(['이름', name])
  const known = new Set(fieldOrder.map(([k]) => k))
  const allKnown = new Set([...PROFILE_IDENTITY, ...PROFILE_INTERROGATION].map(([k]) => k))
  for (const [key, label] of fieldOrder) {
    const val = String(profile[key] ?? '').trim()
    if (!val) continue
    rows.push([label, val])
  }
  if (opts.includeUnknown) {
    for (const [key, raw] of Object.entries(profile)) {
      const val = String(raw ?? '').trim()
      if (!val || allKnown.has(key) || known.has(key)) continue
      rows.push([key, val])
    }
  }
  return rows
}

function ProfileRows({
  rows,
  variant = 'stack',
}: {
  rows: [string, string][]
  variant?: 'grid' | 'stack'
}) {
  if (!rows.length) return <p style={{ color: 'var(--muted)' }}>—</p>
  return (
    <div className={`dossier-facts${variant === 'grid' ? ' is-grid' : ' is-stack'}`}>
      {rows.map(([label, value]) => (
        <div key={label} className="dossier-fact">
          <div className="dossier-fact-label">{label}</div>
          <div className="dossier-fact-value">{value}</div>
        </div>
      ))}
    </div>
  )
}
