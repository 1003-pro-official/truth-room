export type DeskItem = {
  id: string
  file: string
  short: string
  evidence_id: string | null
  query: string
  hint: string
  decoy: boolean
}

export const CLUE_LABELS: Record<string, string> = {
  ev_card_03: '법인카드 · 강남역 룸살롱 결제',
  ev_msg_12: '슬랙 DM · 박신입 서버실 침입',
  ev_net_01: '라운지 Wi-Fi · ~100GB 외부 전송',
  ev_log_07: '출입 로그 · 김팀장 지문',
}

export const CLUE_FLAVOR: Record<string, string> = {
  ev_card_03: '법인카드 전표가 책상 위로 떨어진다.',
  ev_msg_12: '슬랙 DM 캡처가 화면에 고정된다.',
  ev_net_01: '라운지 AP 로그 — 전송량 그래프가 치솟는다.',
  ev_log_07: '서버실 출입 로그가 프린터에서 나온다.',
}

export const EVIDENCE_DESK_ITEMS: DeskItem[] = [
  {
    id: 'ev_card_03',
    file: 'ev_card_03.webp',
    short: '법인카드',
    evidence_id: 'ev_card_03',
    query: '법인카드 룸살롱',
    hint: '결제 전표 · 강남',
    decoy: false,
  },
  {
    id: 'bait_cctv',
    file: 'bait_cctv.webp',
    short: '로비 CCTV',
    evidence_id: null,
    query: '로비 CCTV 23시 타임스탬프 캡처',
    hint: '카메라 캡처 · 23:10',
    decoy: true,
  },
  {
    id: 'ev_msg_12',
    file: 'ev_msg_12.webp',
    short: '슬랙 DM',
    evidence_id: 'ev_msg_12',
    query: '슬랙 DM 박신입 서버실',
    hint: '메신저 캡처',
    decoy: false,
  },
  {
    id: 'bait_vpn',
    file: 'bait_vpn.webp',
    short: 'VPN 로그',
    evidence_id: null,
    query: '해외 VPN 세션 접속 로그 요약',
    hint: '원격 접속 · 세션 기록',
    decoy: true,
  },
  {
    id: 'ev_net_01',
    file: 'ev_net_01.webp',
    short: '네트워크',
    evidence_id: 'ev_net_01',
    query: '라운지 Wi-Fi 100GB',
    hint: '대용량 외부 전송',
    decoy: false,
  },
  {
    id: 'bait_usb',
    file: 'bait_usb.webp',
    short: 'USB 대장',
    evidence_id: null,
    query: '보안팀 USB 대여 반납 대장',
    hint: '대여·반납 기록',
    decoy: true,
  },
  {
    id: 'ev_log_07',
    file: 'ev_log_07.webp',
    short: '출입 로그',
    evidence_id: 'ev_log_07',
    query: '서버실 출입 지문',
    hint: '보안문 기록',
    decoy: false,
  },
  {
    id: 'bait_taxi',
    file: 'bait_taxi.webp',
    short: '택시 전표',
    evidence_id: null,
    query: '강남 개인 택시 영수증 전표',
    hint: '야간 이동 · 강남',
    decoy: true,
  },
  {
    id: 'bait_mail',
    file: 'bait_mail.webp',
    short: '업무 메일',
    evidence_id: null,
    query: '주간 업무보고 사내 메일 회신',
    hint: '사내 메일 출력',
    decoy: true,
  },
  {
    id: 'bait_print',
    file: 'bait_print.webp',
    short: '프린터 로그',
    evidence_id: null,
    query: '복합기 프린터 대기열 출력 로그',
    hint: '출력 대기열 기록',
    decoy: true,
  },
]

export const INVENTORY_SLOT_COUNT = 4

export function shuffleDeskOrder(): string[] {
  const order = EVIDENCE_DESK_ITEMS.map((c) => c.id)
  for (let i = order.length - 1; i > 0; i -= 1) {
    const j = Math.floor(Math.random() * (i + 1))
    ;[order[i], order[j]] = [order[j], order[i]]
  }
  return order
}

export function deskItemsForOrder(order: string[]): DeskItem[] {
  const byId = Object.fromEntries(EVIDENCE_DESK_ITEMS.map((c) => [c.id, c]))
  const items = order.map((id) => byId[id]).filter(Boolean) as DeskItem[]
  for (const c of EVIDENCE_DESK_ITEMS) {
    if (!items.find((x) => x.id === c.id)) items.push(c)
  }
  return items
}
