import { useEffect, useState } from 'react'
import { isBgmOn, playBgm, toggleBgm } from '../audio/sfx'
import { useGameStore } from '../state/gameStore'

export function TopBar() {
  const game = useGameStore((s) => s.game)
  const gameStarted = useGameStore((s) => s.gameStarted)
  const setSidebarOpen = useGameStore((s) => s.setSidebarOpen)
  const sidebarOpen = useGameStore((s) => s.sidebarOpen)
  const [bgmOn, setBgmOn] = useState(false)

  useEffect(() => {
    if (!gameStarted) return
    playBgm().then((ok) => setBgmOn(ok))
  }, [gameStarted])

  const stamina = game?.stamina ?? 0
  const max = game?.stamina_max ?? 3
  const hearts = '♥'.repeat(stamina) + '♡'.repeat(Math.max(0, max - stamina))

  return (
    <header className="topbar">
      <div className="topbar-left">
        <button
          type="button"
          className="burger"
          aria-label="메뉴"
          aria-expanded={sidebarOpen}
          onClick={() => setSidebarOpen(!sidebarOpen)}
        >
          <span className="burger-icon" aria-hidden="true" />
        </button>
        <div className="brand">방구석 프로파일러</div>
      </div>
      <div className="topbar-right">
        <div className="stamina-chip" title={`수사 권한 ${stamina}/${max}`}>
          <span className="lbl">수사 권한</span>
          <span className="hearts">{hearts}</span>
        </div>
        {gameStarted ? (
          <button
            type="button"
            className="bgm-toggle"
            aria-pressed={bgmOn}
            aria-label="배경음악"
            title={bgmOn ? 'BGM ON' : 'BGM OFF'}
            onClick={async () => {
              const on = await toggleBgm()
              setBgmOn(on || isBgmOn())
            }}
          >
            <span className="bgm-eq" aria-hidden="true">
              <span />
              <span />
              <span />
              <span />
            </span>
          </button>
        ) : null}
      </div>
    </header>
  )
}
