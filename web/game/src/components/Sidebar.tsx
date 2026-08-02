import { CLUE_LABELS } from '../data/deskItems'
import { GOLDEN_ROUTE_ACCUSE, GOLDEN_ROUTE_STEPS } from '../data/goldenRoute'
import { useGameStore } from '../state/gameStore'

export function Sidebar() {
  const game = useGameStore((s) => s.game)
  const caseWon = useGameStore((s) => s.caseWon)
  const openHowto = useGameStore((s) => s.openHowto)
  const openCase = useGameStore((s) => s.openCase)
  const restart = useGameStore((s) => s.restart)
  const setSidebarOpen = useGameStore((s) => s.setSidebarOpen)
  const owned = game?.evidence_ids || []
  const ownedSet = new Set(owned)
  const nextStep = GOLDEN_ROUTE_STEPS.find((s) => !ownedSet.has(s.evidence_id))
  const haveN = GOLDEN_ROUTE_STEPS.filter((s) => ownedSet.has(s.evidence_id)).length
  const accuseReady = haveN >= 2 && ownedSet.has('ev_net_01')
  const accuseDone = Boolean(game?.ended && caseWon)

  let hint = '결정적 증거 조합으로 진범 지목'
  if (accuseDone) hint = '클리어 — 자백 엔딩'
  else if (nextStep) hint = `다음: 「${nextStep.query}」`
  else if (accuseReady) hint = `최종 지목 · ${GOLDEN_ROUTE_ACCUSE.short}`

  return (
    <aside className="sidebar">
      <div className="side-nav-header">
        <div className="side-nav-brand-row">
          <p className="side-nav-case">{game?.title || '진실의 방'}</p>
          <button
            type="button"
            className="side-close"
            aria-label="사이드바 닫기"
            onClick={() => setSidebarOpen(false)}
          >
            ×
          </button>
        </div>
      </div>

      <div className="side-block">
        <button type="button" className="side-restart" onClick={() => restart()}>
          새 수사 개시
        </button>
      </div>

      <div className="side-block side-block-menu">
        <button type="button" className="side-btn" onClick={() => openHowto()}>
          게임 방법
        </button>
        <button type="button" className="side-btn" onClick={() => openCase()}>
          사건개요
        </button>
      </div>

      <div className="side-block side-block-divided">
        <p className="side-section-label">골든 루트</p>
        <div className="golden-route">
          <div className="golden-steps">
            {GOLDEN_ROUTE_STEPS.map((step, idx) => {
              const done = ownedSet.has(step.evidence_id)
              const isNext = !done && nextStep?.evidence_id === step.evidence_id
              const cls = done ? 'is-done' : isNext ? 'is-next' : 'is-locked'
              return (
                <div key={step.evidence_id} className={`golden-step ${cls}`} title={step.beat}>
                  <span className="golden-dot">{done ? '✓' : String(idx + 1)}</span>
                  <div className="golden-step-body">
                    <strong>{step.short}</strong>
                    {isNext ? <span className="golden-step-desc">{step.beat}</span> : null}
                  </div>
                </div>
              )
            })}
            <div
              className={`golden-step ${
                accuseDone ? 'is-done' : accuseReady ? 'is-next' : 'is-locked'
              }`}
              title={GOLDEN_ROUTE_ACCUSE.beat}
            >
              <span className="golden-dot">{accuseDone ? '✓' : '4'}</span>
              <div className="golden-step-body">
                <strong>{GOLDEN_ROUTE_ACCUSE.short}</strong>
                {accuseReady && !accuseDone ? (
                  <span className="golden-step-desc">{GOLDEN_ROUTE_ACCUSE.beat}</span>
                ) : null}
              </div>
            </div>
          </div>
          <span className="golden-hint">{hint}</span>
        </div>
      </div>

      <div className="side-block side-block-divided">
        <p className="side-section-label">인벤토리 보관함</p>
        <div className={`inventory-sidebar${owned.length === 0 ? ' is-empty' : ''}`}>
          {owned.length === 0 ? (
            <p className="inv-slot-meta">아직 확보한 증거가 없습니다.</p>
          ) : (
            <div className="inv-slots">
              {owned.slice(0, 4).map((eid, i) => (
                <div key={eid} className="inv-slot is-filled" title={eid}>
                  <span className="inv-slot-num">{i + 1}</span>
                  <span className="inv-slot-name">{CLUE_LABELS[eid] || eid}</span>
                </div>
              ))}
            </div>
          )}
        </div>
      </div>
    </aside>
  )
}
