import { useEffect, useRef } from 'react'
import { sfx } from '../audio/sfx'

type Particle = {
  x: number
  y: number
  vx: number
  vy: number
  life: number
  maxLife: number
  size: number
  color: string
  gravity: number
}

const COLORS = ['#d4af69', '#e8d5a3', '#7a9bb8', '#c5d4e0', '#f0e6d2']

function spawnBurst(cx: number, cy: number, count: number, power = 1): Particle[] {
  const out: Particle[] = []
  for (let i = 0; i < count; i++) {
    const angle = (Math.PI * 2 * i) / count + Math.random() * 0.4
    const speed = (1.6 + Math.random() * 4.2) * power
    out.push({
      x: cx + (Math.random() - 0.5) * 14,
      y: cy + (Math.random() - 0.5) * 14,
      vx: Math.cos(angle) * speed,
      vy: Math.sin(angle) * speed - 1.1 * power,
      life: 0,
      maxLife: 34 + Math.floor(Math.random() * 26),
      size: 1.4 + Math.random() * 2.2,
      color: COLORS[i % COLORS.length],
      gravity: 0.075 + Math.random() * 0.055,
    })
  }
  return out
}

function burstAt(
  w: number,
  h: number,
  strong: boolean,
): Particle[] {
  const cx = w * 0.5
  const cy = h * 0.48
  if (strong) {
    return [
      ...spawnBurst(cx, cy, 28, 1.05),
      ...spawnBurst(cx - w * 0.12, cy + h * 0.04, 16, 0.95),
      ...spawnBurst(cx + w * 0.12, cy + h * 0.04, 16, 0.95),
      ...spawnBurst(cx, cy - h * 0.06, 14, 0.9),
    ]
  }
  const ox = (Math.random() - 0.5) * w * 0.22
  const oy = (Math.random() - 0.5) * h * 0.12
  return [
    ...spawnBurst(cx + ox, cy + oy, 18, 0.82),
    ...spawnBurst(cx + ox * 0.4, cy + oy - h * 0.05, 12, 0.72),
  ]
}

/** 검거 도장 동안 금·청회색 폭죽을 간헐적으로 반복 */
export function ArrestFireworks({ play }: { play: boolean }) {
  const canvasRef = useRef<HTMLCanvasElement>(null)

  useEffect(() => {
    if (!play) return
    const canvas = canvasRef.current
    if (!canvas) return
    const parent = canvas.parentElement
    if (!parent) return

    const dpr = Math.min(window.devicePixelRatio || 1, 2)
    const resize = () => {
      const rect = parent.getBoundingClientRect()
      canvas.width = Math.max(1, Math.floor(rect.width * dpr))
      canvas.height = Math.max(1, Math.floor(rect.height * dpr))
      canvas.style.width = `${rect.width}px`
      canvas.style.height = `${rect.height}px`
    }
    resize()

    const ctx = canvas.getContext('2d')
    if (!ctx) return
    ctx.setTransform(dpr, 0, 0, dpr, 0, 0)

    let w = canvas.width / dpr
    let h = canvas.height / dpr
    let particles: Particle[] = burstAt(w, h, true)
    let raf = 0
    let alive = true
    let nextBurstAt = performance.now() + 2200 + Math.random() * 600

    // 도장과 동시에 시작 — 박수 MP3가 초반 fade-in이라 도장이 가려지지 않음
    sfx.applause()

    const onResize = () => {
      resize()
      w = canvas.width / dpr
      h = canvas.height / dpr
      ctx.setTransform(dpr, 0, 0, dpr, 0, 0)
    }
    window.addEventListener('resize', onResize)

    const tick = (now: number) => {
      if (!alive) return

      if (now >= nextBurstAt) {
        particles = particles.concat(burstAt(w, h, false))
        nextBurstAt = now + 2200 + Math.random() * 800
      }

      ctx.clearRect(0, 0, w, h)
      const next: Particle[] = []
      for (const p of particles) {
        p.life += 1
        if (p.life >= p.maxLife) continue
        p.x += p.vx
        p.y += p.vy
        p.vy += p.gravity
        p.vx *= 0.985
        const t = 1 - p.life / p.maxLife
        ctx.globalAlpha = Math.max(0, t * 0.92)
        ctx.fillStyle = p.color
        ctx.beginPath()
        ctx.arc(p.x, p.y, p.size * (0.55 + t * 0.45), 0, Math.PI * 2)
        ctx.fill()
        next.push(p)
      }
      particles = next
      ctx.globalAlpha = 1

      raf = window.requestAnimationFrame(tick)
    }

    raf = window.requestAnimationFrame(tick)
    return () => {
      alive = false
      window.cancelAnimationFrame(raf)
      window.removeEventListener('resize', onResize)
      ctx.clearRect(0, 0, w, h)
    }
  }, [play])

  if (!play) return null
  return <canvas className="arrest-fireworks" ref={canvasRef} aria-hidden="true" />
}
