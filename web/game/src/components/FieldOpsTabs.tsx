import { useEffect, useRef, useState } from 'react'
import { assetUrl } from '../api/client'
import { CLUE_LABELS } from '../data/deskItems'
import { useGameStore } from '../state/gameStore'

export function FieldOpsTabs() {
  const tab = useGameStore((s) => s.tab)
  const setTab = useGameStore((s) => s.setTab)
  return (
    <div className="ops-col">
      <p className="ops-kicker">Field Ops · Command Deck</p>
      <div className="tabs" role="tablist">
        {(
          [
            ['ask', '심문'],
            ['search', '증거 수색'],
            ['accuse', '최종 지목'],
          ] as const
        ).map(([id, label]) => (
          <button
            key={id}
            type="button"
            className={`tab${tab === id ? ' active' : ''}`}
            onClick={() => setTab(id)}
          >
            {label}
          </button>
        ))}
      </div>
      {tab === 'ask' ? <AskPanel /> : null}
      {tab === 'search' ? <SearchPanel /> : null}
      {tab === 'accuse' ? <AccusePanel /> : null}
    </div>
  )
}

function AskPanel() {
  const game = useGameStore((s) => s.game)
  const chat = useGameStore((s) => s.chat)
  const busy = useGameStore((s) => s.busy)
  const llmDegraded = useGameStore((s) => s.llmDegraded)
  const ask = useGameStore((s) => s.ask)
  const suspectId = useGameStore((s) => s.suspectId)
  const setSuspect = useGameStore((s) => s.setSuspect)
  const [q, setQ] = useState('')
  const logRef = useRef<HTMLDivElement>(null)

  useEffect(() => {
    const el = logRef.current
    if (!el) return
    el.scrollTop = el.scrollHeight
  }, [chat.length, busy])

  if (!game) return null

  return (
    <div className="ops-panel">
      <select
        className="ask-select"
        value={suspectId}
        onChange={(e) => setSuspect(e.target.value)}
        disabled={busy || game.ended}
        aria-label="심문 대상"
      >
        {game.suspects.map((s) => (
          <option key={s.id} value={s.id}>
            {s.name}
          </option>
        ))}
      </select>

      {chat.length > 0 ? (
        <div className="chat-log" ref={logRef}>
          {chat.map((m, i) =>
            m.role === 'system' ? (
              <div
                key={`${m.role}-${i}`}
                className="chat-msg role-system"
                role="status"
              >
                <div className="chat-system-text">{m.content}</div>
              </div>
            ) : (
              <div key={`${m.role}-${i}`} className={`chat-msg role-${m.role}`}>
                <img
                  className="chat-avatar"
                  src={chatAvatarUrl(m)}
                  alt=""
                  onError={(e) => {
                    const img = e.currentTarget
                    if (img.dataset.fallback) return
                    img.dataset.fallback = '1'
                    if (m.role === 'suspect' && m.suspect_id) {
                      img.src = assetUrl(`suspects/${m.suspect_id}.webp`)
                    }
                  }}
                />
                <div className="chat-body">
                  <div className="chat-name">{m.name || roleLabel(m.role)}</div>
                  <div className="chat-text">{m.content}</div>
                </div>
              </div>
            ),
          )}
        </div>
      ) : null}

      <form
        className="composer"
        onSubmit={(e) => {
          e.preventDefault()
          const text = q
          setQ('')
          void ask(text)
        }}
      >
        <input
          type="text"
          value={q}
          onChange={(e) => setQ(e.target.value)}
          placeholder="질문을 입력하세요"
          disabled={busy || game.ended}
          autoComplete="off"
        />
        <button
          type="submit"
          className="send-btn"
          disabled={busy || game.ended || !q.trim()}
          aria-label="전송"
        >
          <svg viewBox="0 0 24 24" width="18" height="18" aria-hidden="true">
            <path
              d="M12 4v14M6.5 10.5 12 4.5l5.5 6"
              fill="none"
              stroke="currentColor"
              strokeWidth="3.2"
              strokeLinecap="round"
              strokeLinejoin="round"
            />
          </svg>
        </button>
      </form>

      {busy ? (
        <div className="ask-spinner" role="status" aria-live="polite">
          <span className="ask-spinner-icon" aria-hidden="true" />
          <span>
            {llmDegraded === 'quota'
              ? 'OpenAI 토큰 소진으로 로컬 답변 중…'
              : llmDegraded === 'auth'
                ? 'OpenAI 키 문제로 로컬 답변 중…'
                : '에이전트 협의 중… (용의자 · 조수 · 심판)'}
          </span>
        </div>
      ) : null}
    </div>
  )
}

function roleLabel(role: string): string {
  if (role === 'user') return '탐정'
  if (role === 'assistant') return '조수'
  if (role === 'suspect') return '용의자'
  return role
}

function chatAvatarUrl(m: {
  role: string
  suspect_id?: string
  portrait_stage?: number
}): string {
  if (m.role === 'user') return assetUrl('characters/detective.webp')
  if (m.role === 'assistant') return assetUrl('characters/assistant.webp')
  const sid = m.suspect_id || ''
  const stage = Math.max(0, Math.min(3, Number(m.portrait_stage || 0)))
  if (sid && stage > 0) return assetUrl(`suspects/${sid}_s${stage}.webp`)
  if (sid) return assetUrl(`suspects/${sid}.webp`)
  return assetUrl('characters/detective.webp')
}

function SearchPanel() {
  const game = useGameStore((s) => s.game)
  const deskItems = useGameStore((s) => s.deskItems)
  const inspected = useGameStore((s) => s.deskInspected)
  const owned = new Set(game?.evidence_ids || [])
  const busy = useGameStore((s) => s.busy)
  const searchDesk = useGameStore((s) => s.searchDesk)
  const setTab = useGameStore((s) => s.setTab)

  const winCount = game?.win_evidence_count ?? 0
  const winTotal = game?.win_evidence_total ?? 3
  const deskCount = game?.desk_evidence_count ?? 0
  const deskTotal = game?.desk_evidence_total ?? 4
  const accuseReady = Boolean(game?.evidence_ready_for_accuse)
  const deskComplete = Boolean(game?.desk_evidence_complete)

  return (
    <div className="ops-panel">
      <p className="hint-muted">
        책상 위 증거 후보를 클릭해 수색하세요. 헛수색 시 수사 권한이 감소합니다.
      </p>
      <p className="desk-progress" role="status">
        지목 핵심 증거{' '}
        <strong>
          {winCount}/{winTotal}
        </strong>
        {' · '}
        책상 실증거{' '}
        <strong>
          {deskCount}/{deskTotal}
        </strong>
        {accuseReady ? ' · 지목 가능' : null}
        {deskComplete ? ' · 책상 수색 완료' : null}
      </p>
      {accuseReady ? (
        <p className="desk-progress-cta">
          <button type="button" className="linkish-btn" onClick={() => setTab('accuse')}>
            최종 지목 탭으로 이동 →
          </button>
        </p>
      ) : null}
      <p className="desk-swipe-hint">좌우로 밀어 책상을 살펴보세요.</p>
      <div className="desk-scroll">
        <div className="desk-board">
          {deskItems().map((item) => {
            const already =
              (!item.decoy && item.evidence_id && owned.has(item.evidence_id)) ||
              inspected.includes(item.id)
            const decoyLocked = item.decoy && deskComplete
            return (
              <button
                key={item.id}
                type="button"
                className={`desk-item${decoyLocked ? ' is-locked' : ''}`}
                disabled={Boolean(already) || decoyLocked || busy || Boolean(game?.ended)}
                title={
                  decoyLocked
                    ? '실증거를 모두 확보했습니다'
                    : item.hint
                }
                style={{
                  backgroundImage: `url(${assetUrl(`ui/evidence_desk/${item.file}`)})`,
                }}
                onClick={() => void searchDesk(item)}
              >
                <span>{item.short}</span>
              </button>
            )
          })}
        </div>
      </div>
    </div>
  )
}

function AccusePanel() {
  const game = useGameStore((s) => s.game)
  const suspectId = useGameStore((s) => s.suspectId)
  const setSuspect = useGameStore((s) => s.setSuspect)
  const accuse = useGameStore((s) => s.accuse)
  const busy = useGameStore((s) => s.busy)
  const [picked, setPicked] = useState<string[]>([])

  if (!game) return null
  const owned = (game.evidence_ids || []).slice(0, 4)

  const toggleEvidence = (eid: string) => {
    setPicked((prev) => {
      if (prev.includes(eid)) return prev.filter((x) => x !== eid)
      if (prev.length >= 2) return prev
      return [...prev, eid]
    })
  }

  return (
    <div className="ops-panel accuse-grid">
      <p className="hint-muted">용의자 1명 + 결정적 증거 정확히 2장</p>
      <select
        className="ask-select"
        value={suspectId}
        onChange={(e) => setSuspect(e.target.value)}
        disabled={busy || game.ended}
        aria-label="지목 대상"
      >
        {game.suspects.map((s) => (
          <option key={s.id} value={s.id}>
            {s.name}
          </option>
        ))}
      </select>
      <div className={`inventory-sidebar accuse-inventory${owned.length === 0 ? ' is-empty' : ''}`}>
        {owned.length === 0 ? (
          <p className="inv-slot-meta">아직 확보한 증거가 없습니다.</p>
        ) : (
          <div className="inv-slots">
            {owned.map((eid, i) => {
              const on = picked.includes(eid)
              const locked = !on && picked.length >= 2
              return (
                <button
                  key={eid}
                  type="button"
                  className={`inv-slot is-filled${on ? ' is-picked' : ''}`}
                  title={eid}
                  disabled={locked || busy || game.ended}
                  onClick={() => toggleEvidence(eid)}
                >
                  <span className="inv-slot-num">{i + 1}</span>
                  <span className="inv-slot-name">{CLUE_LABELS[eid] || eid}</span>
                </button>
              )
            })}
          </div>
        )}
      </div>
      <div className="accuse-actions">
        <button
          type="button"
          className="primary-btn accuse-submit"
          disabled={picked.length !== 2 || busy || game.ended}
          onClick={() => void accuse(picked)}
        >
          {busy ? '판정 중…' : '지목 확정'}
        </button>
      </div>
    </div>
  )
}
