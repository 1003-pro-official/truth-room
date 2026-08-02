export const GOLDEN_ROUTE_STEPS = [
  {
    evidence_id: 'ev_card_03',
    short: '법인카드',
    kicker: 'STEP 01 · CARD',
    query: '법인카드 룸살롱',
    beat: '김팀장 알리바이를 흔드는 결제 전표',
  },
  {
    evidence_id: 'ev_msg_12',
    short: '슬랙 DM',
    kicker: 'STEP 02 · SLACK',
    query: '슬랙 DM 박신입 서버실',
    beat: '박신입을 목격자로 고정하는 DM',
  },
  {
    evidence_id: 'ev_net_01',
    short: '네트워크',
    kicker: 'STEP 03 · NETWORK',
    query: '라운지 Wi-Fi 100GB',
    beat: '라운지 ~100GB 전송 — 결정타',
  },
] as const

export const GOLDEN_ROUTE_ACCUSE = {
  short: '조합 지목',
  kicker: 'STEP 04 · ACCUSE',
  beat: '확보 증거 2장으로 진범을 지목',
  suspect_name: '이대리',
} as const
