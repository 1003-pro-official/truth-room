import { assetUrl } from '../api/client'
import { useGameStore } from '../state/gameStore'
import { ArrestFireworks } from './ArrestFireworks'

function stressStage(breakN: number, pressure: number, broken: boolean): number {
  const p = Math.min(1, Math.max(0, pressure))
  if (broken || breakN >= 3 || p >= 0.75) return 3
  if (breakN >= 2 || p >= 0.45) return 2
  if (breakN >= 1 || p >= 0.15) return 1
  return 0
}

function stressChip(stage: number, breakN: number): string {
  if (stage >= 3) return 'MENTAL BREAK'
  if (stage === 2) return breakN ? `CRACK ${Math.max(breakN, 1)}/3` : 'CRACK'
  if (stage === 1) return breakN ? `STRESS ${breakN}/3` : 'STRESS'
  return ''
}

export function SuspectCard() {
  const game = useGameStore((s) => s.game)
  const suspectId = useGameStore((s) => s.suspectId)
  const openDossier = useGameStore((s) => s.openDossier)
  const arrestStamp = useGameStore((s) => s.arrestStamp)
  const arrestSlam = useGameStore((s) => s.arrestSlam)

  if (!game) return null
  const suspects = game.suspects || []
  const current = suspects.find((s) => s.id === suspectId) || suspects[0]
  const press = Number(game.pressure?.[suspectId] || 0)
  const br = Number(game.break_count?.[suspectId] || 0)
  const broken = (game.mental_break_suspects || []).includes(suspectId)
  const stage = stressStage(br, press, broken)
  const pct = Math.round(Math.min(1, Math.max(0, press)) * 100)
  const chip = stressChip(stage, br)

  const portrait =
    stage > 0
      ? assetUrl(`suspects/${suspectId}_s${stage}.webp`)
      : assetUrl(`suspects/${suspectId}.webp`)

  const border =
    stage >= 3
      ? '2px solid rgba(180, 70, 80, 0.85)'
      : stage === 2
        ? '2px solid rgba(160, 90, 90, 0.55)'
        : '1px solid rgba(200,210,220,0.14)'

  return (
    <div className="suspect-col">
      <p className="suspect-heading">대상 용의자</p>
      <div className="suspect-portrait-stage">
        <div className={`suspect-pick-wrap stress-${stage}`} style={{ border }}>
          <img className="portrait" src={portrait} alt={current?.name || '용의자'} />
          {chip ? <span className="stress-chip">{chip}</span> : null}
          <button type="button" className="profile-pill" onClick={() => openDossier()}>
            프로필
          </button>
          <div className="portrait-pressure">
            <div className="portrait-pressure-meta">
              <span>PRESSURE</span>
              <span>{pct}%</span>
            </div>
            <div className="portrait-pressure-track">
              <div className="portrait-pressure-fill" style={{ width: `${pct}%` }} />
            </div>
          </div>
          {arrestStamp ? (
            <div className={`arrest-stamp${arrestSlam ? ' is-slam' : ' is-static'}`}>
              <img src={assetUrl('ui/arrest_stamp.webp')} alt="검거" />
            </div>
          ) : null}
        </div>
        <ArrestFireworks play={Boolean(arrestStamp)} />
      </div>
      <div className="suspect-name-plate">
        {current?.name || '용의자'}
        {broken ? ' · 붕괴' : ''}
      </div>
    </div>
  )
}
