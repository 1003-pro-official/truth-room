import { assetUrl } from '../api/client'

const VOL_BGM = 0.06

let bgm: HTMLAudioElement | null = null
let bgmMuted = false
let bgmAudible = false

export function ensureBgm(): HTMLAudioElement {
  if (!bgm) {
    bgm = new Audio(assetUrl('audio/game.mp3'))
    bgm.loop = true
    bgm.preload = 'auto'
    bgm.volume = VOL_BGM
  }
  return bgm
}

export async function playBgm(): Promise<boolean> {
  if (bgmMuted) {
    ensureBgm().pause()
    bgmAudible = false
    return false
  }
  const a = ensureBgm()
  a.volume = VOL_BGM
  try {
    await a.play()
    bgmAudible = true
    return true
  } catch {
    bgmAudible = false
    return false
  }
}

export function stopBgm(): void {
  ensureBgm().pause()
  bgmAudible = false
}

export async function toggleBgm(): Promise<boolean> {
  if (bgmAudible && !ensureBgm().paused && !bgmMuted) {
    bgmMuted = true
    stopBgm()
    return false
  }
  bgmMuted = false
  return playBgm()
}

export function isBgmOn(): boolean {
  return bgmAudible && !ensureBgm().paused && !bgmMuted
}

const debounceAt = new Map<string, number>()

/** 오디오 파일 교체 시 브라우저 캐시 우회용 (숫자만 올리면 됨) */
const SFX_CACHE_BUST = '3'

export function playSfx(
  file: string,
  opts?: { volume?: number; debounceMs?: number; mark?: string },
): void {
  const mark = opts?.mark || file
  const deb = opts?.debounceMs || 0
  const now = Date.now()
  if (deb > 0) {
    const prev = debounceAt.get(mark) || 0
    if (now - prev < deb) return
    debounceAt.set(mark, now)
  }
  const url = `${assetUrl(`audio/${file}`)}?v=${SFX_CACHE_BUST}`
  const a = new Audio(url)
  a.volume = opts?.volume ?? 0.7
  a.play().catch(() => {})
}

export const sfx = {
  uiOpen: () => playSfx('ui_open.mp3', { volume: 0.36, debounceMs: 250, mark: 'ui_open' }),
  searchOk: () => playSfx('sfx_ok.mp3', { volume: 0.75, debounceMs: 200, mark: 'ok' }),
  searchMiss: () => playSfx('sfx_miss.mp3', { volume: 0.7, debounceMs: 200, mark: 'miss' }),
  revoked: () => playSfx('sfx_revoked.mp3', { volume: 0.85, debounceMs: 400, mark: 'revoked' }),
  stress: (stage = 1) =>
    playSfx('sfx_stress_up.mp3', {
      volume: Math.min(0.95, 0.55 + 0.1 * Math.max(0, stage)),
      debounceMs: 180,
      mark: 'stress',
    }),
  stamp: () => playSfx('arrest_stamp.mp3', { volume: 1, debounceMs: 800, mark: 'stamp' }),
  applause: () =>
    playSfx('sfx_applause.mp3', { volume: 1, debounceMs: 6000, mark: 'applause' }),
}
