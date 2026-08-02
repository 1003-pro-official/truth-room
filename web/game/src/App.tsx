import { useEffect } from 'react'
import { playBgm } from './audio/sfx'
import { DialogHost } from './components/DialogHost'
import { FieldOpsTabs } from './components/FieldOpsTabs'
import { Sidebar } from './components/Sidebar'
import { SuspectCard } from './components/SuspectCard'
import { TopBar } from './components/TopBar'
import { useGameStore } from './state/gameStore'

export function App() {
  const boot = useGameStore((s) => s.boot)
  const loading = useGameStore((s) => s.loading)
  const bootError = useGameStore((s) => s.bootError)
  const gameStarted = useGameStore((s) => s.gameStarted)
  const sidebarOpen = useGameStore((s) => s.sidebarOpen)
  const game = useGameStore((s) => s.game)

  useEffect(() => {
    void boot()
  }, [boot])

  useEffect(() => {
    const onKey = (e: KeyboardEvent) => {
      const key = e.key || ''
      const refresh =
        key === 'F5' || ((e.metaKey || e.ctrlKey) && key.toLowerCase() === 'r')
      if (!refresh) return
      e.preventDefault()
      window.location.replace('/')
    }
    window.addEventListener('keydown', onKey, true)
    return () => window.removeEventListener('keydown', onKey, true)
  }, [])

  useEffect(() => {
    if (gameStarted) void playBgm()
  }, [gameStarted])

  if (loading) {
    return <div className="boot-screen">세션 준비 중…</div>
  }

  if (bootError && !game) {
    return (
      <div className="boot-screen">
        <p>세션 생성 실패: {bootError}</p>
        <button type="button" className="primary-btn" onClick={() => void boot()}>
          다시 시도
        </button>
      </div>
    )
  }

  return (
    <div className="app-shell">
      <TopBar />
      <div className={`layout${sidebarOpen ? ' with-sidebar' : ''}`}>
        <Sidebar />
        {gameStarted ? (
          <main className="main-stage">
            {bootError ? <div className="error-banner">{bootError}</div> : null}
            <div className="stage-row">
              <SuspectCard />
              <FieldOpsTabs />
            </div>
          </main>
        ) : (
          <main className="main-stage" aria-hidden="true" />
        )}
      </div>
      <DialogHost />
    </div>
  )
}
