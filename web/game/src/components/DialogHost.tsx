import { assetUrl } from '../api/client'
import { CLUE_FLAVOR, CLUE_LABELS } from '../data/deskItems'
import { GOLDEN_ROUTE_STEPS } from '../data/goldenRoute'
import { useGameStore } from '../state/gameStore'
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
      <Modal title="수색 결과" dismissible={false} alert>
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

  return null
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
