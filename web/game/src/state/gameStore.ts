import { create } from 'zustand'
import {
  api,
  type CaseOverview,
  type Clue,
  type GameState,
  type SuspectProfile,
} from '../api/client'
import {
  CLUE_LABELS,
  deskItemsForOrder,
  shuffleDeskOrder,
  type DeskItem,
} from '../data/deskItems'
import { sfx } from '../audio/sfx'

export type ChatMsg = {
  role: 'user' | 'suspect' | 'assistant' | 'system'
  name?: string
  content: string
  suspect_id?: string
  portrait_stage?: number
}

export type ModalKind =
  | null
  | 'briefing'
  | 'howto'
  | 'case'
  | 'dossier'
  | 'desk_alert'
  | 'desk_clue'
  | 'accuse'
  | 'revoked'

type DeskAlert = { kind: 'ok' | 'warn' | 'info' | 'error'; text: string }

type AccuseFlash = { text: string; won: boolean; revoked: boolean }

type GameStore = {
  bootError: string | null
  loading: boolean
  game: GameState | null
  caseInfo: CaseOverview | null
  gameStarted: boolean
  suspectId: string
  deskOrder: string[]
  deskInspected: string[]
  chat: ChatMsg[]
  pendingClues: Clue[]
  portraitStage: Record<string, number>
  modal: ModalKind
  dossier: SuspectProfile | null
  deskAlert: DeskAlert | null
  accuseFlash: AccuseFlash | null
  revokedMsg: string | null
  caseWon: boolean
  arrestStamp: boolean
  arrestSlam: boolean
  sidebarOpen: boolean
  tab: 'ask' | 'search' | 'accuse'
  busy: boolean
  /** OpenAI 폴백 감지 후 — 대기 문구를 로컬 모드로 전환 */
  llmDegraded: null | 'quota' | 'auth'

  boot: () => Promise<void>
  startGame: () => void
  setSuspect: (id: string) => void
  setTab: (t: 'ask' | 'search' | 'accuse') => void
  setSidebarOpen: (v: boolean) => void
  openHowto: () => void
  openCase: () => Promise<void>
  openDossier: () => Promise<void>
  closeModal: () => void
  ask: (question: string) => Promise<void>
  searchDesk: (item: DeskItem) => Promise<void>
  confirmClue: () => void
  accuse: (evidenceIds: string[]) => Promise<void>
  ackAccuse: () => void
  ackRevoked: () => void
  restart: () => Promise<void>
  deskItems: () => DeskItem[]
}

function stressStage(breakN: number, pressure: number, broken: boolean): number {
  const p = Math.min(1, Math.max(0, pressure))
  if (broken || breakN >= 3 || p >= 0.75) return 3
  if (breakN >= 2 || p >= 0.45) return 2
  if (breakN >= 1 || p >= 0.15) return 1
  return 0
}

function sessionFromQuery(): string | null {
  return new URLSearchParams(window.location.search).get('session_id')
}

export const useGameStore = create<GameStore>((set, get) => ({
  bootError: null,
  loading: true,
  game: null,
  caseInfo: null,
  gameStarted: false,
  suspectId: '',
  deskOrder: [],
  deskInspected: [],
  chat: [],
  pendingClues: [],
  portraitStage: {},
  modal: null,
  dossier: null,
  deskAlert: null,
  accuseFlash: null,
  revokedMsg: null,
  caseWon: false,
  arrestStamp: false,
  arrestSlam: false,
  sidebarOpen: false,
  tab: 'ask',
  busy: false,
  llmDegraded: null,

  deskItems: () => deskItemsForOrder(get().deskOrder),

  boot: async () => {
    set({ loading: true, bootError: null, llmDegraded: null })
    try {
      const qSid = sessionFromQuery()
      let game: GameState
      if (qSid) {
        try {
          game = await api.getSession(qSid)
        } catch {
          game = await api.createSession()
        }
      } else {
        game = await api.createSession()
      }
      const caseInfo = await api.getCase(game.session_id)
      const sid = game.suspects[0]?.id || ''
      const url = new URL(window.location.href)
      url.searchParams.set('session_id', game.session_id)
      window.history.replaceState({}, '', url.toString())
      set({
        game,
        caseInfo,
        suspectId: sid,
        deskOrder: shuffleDeskOrder(),
        loading: false,
        modal: 'briefing',
        gameStarted: false,
      })
    } catch (e) {
      set({
        loading: false,
        bootError: e instanceof Error ? e.message : String(e),
      })
    }
  },

  startGame: () => {
    set({ gameStarted: true, modal: null })
  },

  setSuspect: (id) => set({ suspectId: id }),
  setTab: (t) => set({ tab: t }),
  setSidebarOpen: (v) => set({ sidebarOpen: v }),

  openHowto: () => {
    sfx.uiOpen()
    set({ modal: 'howto' })
  },

  openCase: async () => {
    const g = get().game
    if (!g) return
    sfx.uiOpen()
    try {
      const caseInfo = await api.getCase(g.session_id)
      set({ caseInfo, modal: 'case' })
    } catch (e) {
      set({ bootError: e instanceof Error ? e.message : String(e) })
    }
  },

  openDossier: async () => {
    const g = get().game
    const suspectId = get().suspectId
    if (!g || !suspectId) return
    sfx.uiOpen()
    try {
      const dossier = await api.getProfile(g.session_id, suspectId)
      set({ dossier, modal: 'dossier' })
    } catch (e) {
      set({ bootError: e instanceof Error ? e.message : String(e) })
    }
  },

  closeModal: () => {
    const m = get().modal
    if (m === 'briefing' && !get().gameStarted) return
    set({ modal: null, deskAlert: null })
  },

  ask: async (question) => {
    const g = get().game
    const suspectId = get().suspectId
    if (!g || !suspectId || g.ended || get().busy) return
    const q = question.trim()
    if (!q) return
    set({ busy: true })
    try {
      const data = await api.ask(g.session_id, { suspect_id: suspectId, question: q })
      const state = data.state
      const name = state.suspects.find((s) => s.id === suspectId)?.name || suspectId
      const press = Number(state.pressure?.[suspectId] || 0)
      const br = Number(state.break_count?.[suspectId] || 0)
      const broken = (state.mental_break_suspects || []).includes(suspectId)
      const stage = stressStage(br, press, broken)
      const prev = get().portraitStage[suspectId] || 0
      if (stage > prev) sfx.stress(stage)
      let line = data.answer || ''
      line = line
        .replace(/\s*\(질문\s*요약:\s*[^)]*\)\s*$/u, '')
        .replace(/\s*\(질문:\s*[^)]*\)\s*$/u, '')
        .trim()
      if (data.is_alibi_broken) {
        line = `알리바이 붕괴! (break ${data.break_count}/3) — ${line}`
      }
      const chat = [
        ...get().chat,
        { role: 'user' as const, name: '탐정', content: q },
        {
          role: 'suspect' as const,
          name,
          content: line,
          suspect_id: suspectId,
          portrait_stage: stage,
        },
      ]
      if (data.assistant_note?.trim()) {
        chat.push({
          role: 'assistant',
          name: '조수',
          content: data.assistant_note.trim(),
        })
      }
      const notice = String(data.llm_notice || '').trim()
      let llmDegraded = get().llmDegraded
      if (notice.includes('토큰 소진')) llmDegraded = 'quota'
      else if (notice.includes('키 문제')) llmDegraded = 'auth'
      set({
        game: state,
        chat,
        portraitStage: { ...get().portraitStage, [suspectId]: stage },
        busy: false,
        llmDegraded,
      })
    } catch (e) {
      set({
        busy: false,
        bootError: e instanceof Error ? e.message : String(e),
      })
    }
  },

  searchDesk: async (item) => {
    const g = get().game
    if (!g || g.ended || get().busy) return
    set({ busy: true })
    const inspected = get().deskInspected.includes(item.id)
      ? get().deskInspected
      : [...get().deskInspected, item.id]
    try {
      const data = await api.search(g.session_id, {
        query: item.query,
        force_miss: Boolean(item.decoy),
        force_evidence_id: item.decoy ? null : item.evidence_id,
      })
      const state = data.state
      if (data.authority_revoked) {
        sfx.revoked()
        set({
          game: state,
          deskInspected: inspected,
          busy: false,
          modal: 'revoked',
          revokedMsg:
            data.ending ||
            '감사관, 당신은 무능합니다. 수사 권한이 박탈되었습니다.',
        })
        return
      }
      if (data.useless_search) {
        sfx.searchMiss()
        set({
          game: state,
          deskInspected: inspected,
          busy: false,
          modal: 'desk_alert',
          deskAlert: {
            kind: 'warn',
            text: `헛수색 — 「${item.short}」에서는 단서를 찾지 못했습니다.`,
          },
        })
        return
      }
      if (data.already_owned) {
        set({
          game: state,
          deskInspected: inspected,
          busy: false,
          modal: 'desk_alert',
          deskAlert: { kind: 'info', text: '이미 확보한 증거입니다.' },
        })
        return
      }
      sfx.searchOk()
      const clues = data.new_clues || []
      if (clues.length) {
        set({
          game: state,
          deskInspected: inspected,
          pendingClues: clues,
          busy: false,
          modal: 'desk_clue',
        })
      } else {
        const hit0 = ((data.hits || [])[0] || {}) as Record<string, unknown>
        const eid = String(hit0.evidence_id || '')
        let title = String(hit0.snippet || eid || item.short || '수색 완료')
        if (title.split(',').length > 3 || title.includes('\n')) {
          title = CLUE_LABELS[eid] || item.short || '수색 완료'
        }
        set({
          game: state,
          deskInspected: inspected,
          busy: false,
          modal: 'desk_alert',
          deskAlert: { kind: 'ok', text: `수색 완료 — ${title}` },
        })
      }
    } catch (e) {
      set({
        busy: false,
        bootError: e instanceof Error ? e.message : String(e),
      })
    }
  },

  confirmClue: () => {
    const pending = [...get().pendingClues]
    pending.shift()
    set({
      pendingClues: pending,
      modal: pending.length ? 'desk_clue' : null,
    })
  },

  accuse: async (evidenceIds) => {
    const g = get().game
    const suspectId = get().suspectId
    if (!g || !suspectId || evidenceIds.length !== 2 || get().busy) return
    set({ busy: true })
    try {
      const data = await api.accuse(g.session_id, {
        suspect_id: suspectId,
        evidence_ids: evidenceIds,
      })
      const ending = (data.ending || '').trim()
      if (data.correct) {
        sfx.searchOk()
        set({
          game: data.state,
          busy: false,
          modal: 'accuse',
          accuseFlash: {
            text: ending || '미션 클리어.',
            won: true,
            revoked: false,
          },
        })
      } else if (data.authority_revoked) {
        sfx.revoked()
        set({
          game: data.state,
          busy: false,
          modal: 'accuse',
          accuseFlash: {
            text:
              ending ||
              '감사관, 당신은 무능합니다. 수사 권한이 박탈되었습니다.',
            won: false,
            revoked: true,
          },
        })
      } else {
        sfx.searchMiss()
        set({
          game: data.state,
          busy: false,
          modal: 'accuse',
          accuseFlash: {
            text: ending || '지목이 빗나갔습니다. 조합을 다시 검토하세요.',
            won: false,
            revoked: false,
          },
        })
      }
    } catch (e) {
      set({
        busy: false,
        bootError: e instanceof Error ? e.message : String(e),
      })
    }
  },

  ackAccuse: () => {
    const flash = get().accuseFlash
    if (flash?.won) {
      sfx.stamp()
      set({
        modal: null,
        accuseFlash: null,
        caseWon: true,
        arrestStamp: true,
        arrestSlam: true,
      })
      return
    }
    if (flash?.revoked) {
      set({
        modal: null,
        accuseFlash: null,
        revokedMsg: flash.text,
      })
      // show revoked card via ending banner path — keep modal closed, show banner
      set({ modal: 'revoked', revokedMsg: flash.text })
      return
    }
    set({ modal: null, accuseFlash: null })
  },

  ackRevoked: () => set({ modal: null, revokedMsg: null }),

  restart: async () => {
    set({
      chat: [],
      pendingClues: [],
      deskInspected: [],
      portraitStage: {},
      caseWon: false,
      arrestStamp: false,
      arrestSlam: false,
      modal: null,
      accuseFlash: null,
      revokedMsg: null,
      deskAlert: null,
      gameStarted: false,
      tab: 'ask',
      llmDegraded: null,
    })
    await get().boot()
  },
}))
