#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""generate_rag_dataset.py — RAG 데이터셋 스펙에 맞춰 data/raw 생성

스펙:
- 진술 3인: 인당 약 1,000~1,500자
- 현장/CCTV 기술: 약 800자 × 1~2
- 메신저: 3,000~5,000줄 (사건±1주 밀도 + 노이즈)
- 출입 로그: 10,000~20,000줄
- 법인카드 CSV: 500~1,000줄
- 네트워크 로그: Smoking Gun + 노이즈

기존 evidence_id (ev_card_03, ev_msg_12, ev_log_07, ev_net_01) 유지.
"""

from __future__ import annotations

import csv
import json
import random
import shutil
from datetime import datetime, timedelta
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
RAW = ROOT / "data" / "raw"
RNG = random.Random(42)

EMPLOYEES = [
    ("E-A", "김팀장"),
    ("E-B", "이대리"),
    ("E-C", "박신입"),
    ("E-D", "윤사원"),
    ("E-E", "정대리"),
    ("E-F", "한과장"),
    ("E-G", "오주임"),
    ("E-H", "신인턴"),
    ("E-I", "배수석"),
    ("E-J", "조연구원"),
]

NOISE_CHAT = [
    "점심 뭐 먹지",
    "오늘 야근이야?",
    "커피 한 잔 어때",
    "회의실 비었나",
    "주말에 비 온다더라",
    "노트북 충전기 빌릴 수 있어?",
    "슬랙 알림 너무 많다",
    "퇴근하고 싶다",
    "문서 공유 부탁",
    "PR 리뷰 해줘",
    "테스트 서버 죽었나",
    "오메가 학습 로그 봤어?",
]


def reset_raw() -> None:
    if RAW.exists():
        shutil.rmtree(RAW)
    for sub in ("statements", "forensics", "messenger", "logs", "corporate_card", "network"):
        (RAW / sub).mkdir(parents=True, exist_ok=True)


def _pad_to(text: str, min_chars: int, extras: list[str]) -> str:
    """스펙 최소 글자 수까지 문단을 이어 붙인다."""
    body = text.strip()
    i = 0
    while len(body) < min_chars and extras:
        body = body + "\n\n" + extras[i % len(extras)]
        i += 1
        if i > 20:
            break
    return body


def write_statements() -> None:
    kim = """# 김팀장 진술서 (2026-07-30 오전 청취)

저는 인프라와 기획을 총괄하는 김팀장입니다. 사건 당일(2026년 7월 29일) 일정을 정리하면, 오후 2시부터 5시까지는 경영진 브리핑용 차기 로드맵 슬라이드를 수정했고, 저녁 식사 뒤에는 사무실로 돌아와 **23시부터 자정까지 자기 자리에서 발표용 기획안을 꼼꼼히 검토**했다고 기억합니다. PC 문서 자동저장·버전 히스토리만 보시면 아실 겁니다. 나 때는 야근이 미덕이었고, 팀원들이 흔들리면 안 되니까 자리를 지키는 시늉이라도 해야 한다고 생각했습니다. 책임은 위에서 지는 척하면서 실무는 아래로 미루는 문화가 문제인데, 그걸 제가 만들었다고 몰아가진 마십시오. 그날 비도 많이 와서 외출할 마음도 없었습니다.

이대리에 대해서는 실력은 인정하지만 태도가 까칠하고, 공로를 혼자 가져가려 한다는 불만이 팀에 있습니다. 보너스 시즌마다 마찰이 있었고, 제가 학습 파이프라인 성과를 기획 관점에서 요약했다고 해서 도둑질이라고 부르는 건 과합니다. 박신입은 입사 3개월이라 실수가 잦고, 그날도 배가 아프다며 자주 자리를 비웠습니다. 서버실 출입은 원칙상 팀장급 승인인데, 제가 23시 전후에 서버실에 들어간 기억은 없습니다. 지문·배지 로그에 제 이름이 찍혀 있다면 기기 오류이거나 누군가 제 배지를 쓴 것일 수 있습니다. 법인카드는 제가 관리하는 공용 카드라 평소 소지합니다만, 그날 밤 사용 내역은 업무 접대 관련으로 설명할 수 있는 범위라고만 하겠습니다. 세부 상호는 회계 쪽에 맡기겠습니다. 카드 분실 신고는 하지 않았고, 책상 서랍에 두었을 가능성도 있습니다.

Omega 가중치 파일을 훔칠 기술적 동기나 외부 접촉은 제게 없습니다. 저는 모델 학습 코드를 직접 돌리지 않고, 인프라 권한과 일정 관리가 주입니다. 경쟁사와 접촉했다는 루머는 사실무근입니다. 범인은 외부 침투이거나, 실무 접근 권한이 큰 쪽을 먼저 보셔야 합니다. CCTV가 결측이라고 해서 저를 용의선에 오래 묶어 두는 것은 시간 낭비입니다. 조사에 협조할 의향은 있으나, 추측성 압박에는 응하지 않겠습니다. 필요한 자료는 법무·보안 팀과 협의해 제공하겠습니다.
"""
    lee = """# 이대리 진술서 (2026-07-30 오전 청취)

저는 Omega 학습 파이프라인과 체크포인트 관리를 담당한 이대리입니다. 7월 29일 저녁 10시 30분경 코딩을 마무리했고, **23시부터 자정까지는 3층 라운지에서 노이즈캔슬링 헤드폰을 끼고 넷플릭스**를 봤습니다. 라운지 CCTV와 AP 연결 기록을 확인하시면 됩니다. 서버실 출입 로그(지문)를 보시면 제 이름은 없을 겁니다. 그 시간대 기록에 김팀장 배지·지문이 찍혀 있다면, 그쪽을 먼저 조사하는 게 맞습니다. 저는 흔적을 안 남기는 쪽으로 일하지, 바보같이 로그에 이름을 남기지 않습니다—이건 비유입니다. 오해하지 마십시오. 라운지에서 자리를 옮긴 적은 거의 없고, 커피를 뽑으러 간 정도입니다.

김팀장은 공로는 가져가고 실무는 떠넘기는 스타일입니다. 보너스 배분도 불공정했고, 제가 만든 학습 코드를 자기 실적으로 포장한 적도 있습니다. 박신입은 그날 화장실이니 마라탕이니 말을 바꿨고, 서버실 근처를 기웃거렸다는 소문도 있습니다. 신입이 기술 유출을 주도했을 가능성은 낮지만, 목격자라면 진술이 흔들린다는 점만은 분명히 해야 합니다. 저는 라운지에 있었고 대용량 외부 전송 같은 건 해본 적 없습니다. 개인 노트북은 업무용으로도 쓰지만, 100GB급 파일을 밖으로 뺀다는 상상은 황당합니다. 넷플릭스 시청 중 배터리 때문에 콘센트에 꽂아 둔 것은 맞습니다.

네트워크 로그를 들이밀기 전에는 추측으로 몰아가지 마십시오. 기술적으로 Omega 가중치를 빼내려면 학습 노드와 내부망 권한이 필요한데, 그 권한은 저와 일부 인프라만 갖고 있습니다. 그렇다고 제가 범인이라는 뜻은 절대 아닙니다. 권한과 범행은 다릅니다. 증거 없이 압박하지 마세요. 필요하다면 라운지 체류 시간과 시청 기록을 제출할 수 있습니다. 동기 면에서도 회사를 배신할 이유는 없습니다—불만은 있어도 유출은 아닙니다.
"""
    park = """# 박신입 진술서 (2026-07-30 오전 청취)

입사 3개월 차 박입니다. 솔직히 너무 무섭고 혼란스럽습니다. 저녁에 마라탕을 먹어서 배가 아팠고, **처음에는 11시부터 계속 3층 남자 화장실에 있었다**고 말했습니다. 사실… 불안해서 서버실 쪽을 몰래 보러 간 적이 있습니다. 문 근처에서 타이핑 소리 같은 게 들렸고, 누군가 더 있는 것 같았습니다. 손이 떨려서 동료 윤사원에게 슬랙으로 짧게 알렸는데, 화장실 알리바이랑 안 맞는 거 압니다. 죄송합니다. 거짓말을 하려던 게 아니라 혼날까 봐 줄였습니다. 다시 진술할 기회를 주셔서 감사합니다. 그날 팀 분위기가 이상해서 호기심과 공포가 동시에 있었습니다.

김팀장은 그날 밤 자리를 비운 것 같다는 얘기가 돌았고, 이대리는 라운지에만 있었다고 하는데 서버실 쪽 인기척과 시간이 겹치는 느낌이 들었습니다. 저는 파일을 옮길 권한도 지식도 없습니다. Omega라는 이름도 회의에서 처음 자세히 들었습니다. 다만 본 것을 숨기면 안 될 것 같아 다시 진술합니다. 복도에서 **우산으로 얼굴을 가린 사람**을 스치듯 본 것도 같습니다. 정확한 시각은 23시 전후입니다. 우산 때문에 얼굴은 못 봤고, 키나 옷차림도 확실하지 않습니다. 발소리는 빨랐고, 서버실 쪽으로 가는 방향이었습니다. 감사관님이 보호해 주신다면 기억나는 대로 계속 협력하겠습니다. 추가 질문에도 솔직히 답하겠습니다. 제가 범인이 아니라는 것만은 분명히 말씀드립니다.
"""
    pads = {
        "suspect_a_kim.md": [
            "추가로 말씀드리면, 저는 사건 전후 일주일간 외부 미팅 일정이 거의 없었고 사내 일정표에도 그렇게 남아 있습니다. 알리바이를 조작할 이유도, 방법도 없다고 생각합니다.",
            "마지막으로, 수사 편의를 위해 제 자리 PC와 메일 아카이브 열람에는 동의합니다. 다만 유무죄 단정 없이 객관 증거 위주로 진행해 주시길 요청합니다.",
        ],
        "suspect_b_lee.md": [
            "라운지에서 본 드라마 제목까지는 기억나지 않지만, 에피소드 길이와 광고 타이밍으로 대략 한 시간을 채웠습니다. 중간에 화장실을 간 적은 한 번뿐이고 서버실 쪽은 가지 않았습니다.",
            "보안팀에서 노트북 포렌식을 원하시면 협조하겠습니다. 다만 사전 통지 없는 압수수색 분위기로 몰아가는 것은 부당합니다. 저는 범인이 아닙니다.",
        ],
        "suspect_c_park.md": [
            "슬랙 메시지는 23:20 전후에 보냈고, 윤사원이 바로 답장한 것으로 기억합니다. 그 직후 너무 무서워서 자리로 돌아갔는지 화장실로 갔는지 기억이 흐릿합니다.",
            "입사 초라 보안 규정도 잘 몰랐고, 서버실 출입 금지 안내를 제대로 숙지하지 못한 점은 반성합니다. 하지만 가중치를 빼내거나 외부로 보낸 적은 절대 없습니다.",
        ],
    }
    for name, body in (
        ("suspect_a_kim.md", kim),
        ("suspect_b_lee.md", lee),
        ("suspect_c_park.md", park),
    ):
        path = RAW / "statements" / name
        text = _pad_to(body, 1100, pads[name]) + "\n"
        path.write_text(text, encoding="utf-8")
        print(f"  statements/{name}: {len(text.strip())} chars")


def write_forensics() -> None:
    cctv = """# 현장 CCTV / 복도 영상 기술서 (포렌식)

작성: 외부 디지털 포렌식 감사관 보조 기록 · 대상일 2026-07-29 · 작성일 2026-07-30

23:00~24:00 구간 로비·서버실 전용 카메라는 폭우와 순간 정전으로 다수 결측이다. NVR 타임라인상 결측은 대략 23:02~23:18, 23:27~23:40에 집중된다. UPS 이벤트와 카메라 채널 드롭 시각이 초 단위로 근접한다. 복구된 3층 복도 카메라 partial 프레임을 기술하면 다음과 같다. **23:05경, 우산으로 얼굴을 가린 미확인 인물이 서버실 전면 복도를 빠른 걸음으로 통과**했다. 성별·신장은 특정 불가하며, 우산 각도 때문에 얼굴 ROI가 확보되지 않았다. 상의는 어두운 색으로 보이며 배지 인식은 불가하다. 우산은 접히지 않은 상태로 얼굴 전면을 가렸다. 23:19경에는 후드티 차림의 신입 추정 인물이 서버실 방향에서 서성이다 이탈했다. 23:31경 엘리베이터 홀에서 중년 남성(김팀장 외형과 유사)이 하차 후 건물 외출하는 장면이 있다. 라운지 방향 카메라는 23시 전후 좌석에 헤드폰 착용 인물이 장시간 앉아 있는 장면이 일부 남아 있으나, 얼굴은 하향이라 확정 불가하다. 본 기술서는 시각 증거 요약이며, 출입·네트워크 로그와 교차검증할 것. 원본 영상은 증거물 목록 F-CCTV-01로 봉인한다.
"""
    scene = """# 현장 초동 임장 메모 (포렌식 보조)

임장 시각: 2026-07-30 01:10 · 장소: 3층 서버실·라운지·복도 · 기상: 호우 잔여

Omega 학습 랙 앞 콘솔에 미완료 세션 흔적이 남아 있었고, 마지막 입력 시각은 시스템 시계 기준 23시대로 추정된다. 바닥 케이블 정리 상태는 양호하며 물리적 침입 흔적(문짝 손상·강제 개방)은 없다. 서버실 보안문 지문 리더 외관 이상 없음. 리더 주변 습기 흔적은 있으나 조작 흔적으로 단정할 수준은 아니다. 라운지 AP(lounge-ap-01) LED 정상, 전원 재부팅 흔적은 없다. 사건 창은 23:00~24:00, 잔류 인원 공식 명단은 김팀장·이대리·박신입이다. 정전 로그와 CCTV 결측 구간이 겹친다. 추가 압수수색 대상: 이대리 개인 노트북, 김팀장 법인카드 영수증, 박신입 휴대폰 슬랙 캐시. 샘플링한 먼지·지문은 연구소로 이첩한다. 현장 사진·스케치는 별첨 S-01~S-08.
"""
    cctv_pads = [
        "프레임 추출 해상도는 1280x720이며, 저조도 노이즈로 인해 얼굴 재식별 모델 적용은 보류한다. 우산 반사광이 렌즈 플레어를 유발한 구간이 있다.",
        "동일 시간대 로비 카메라는 전원 복구 후에도 블랙아웃이 지속되어 별도 벤더 진단을 요청했다. 본 문서는 1차 기술 요약본이다.",
    ]
    scene_pads = [
        "임장 시 서버실 내부 온도는 정상 범위였고, 화재 감지기 이상 알람은 없었다. 콘솔 주변에서 USB 잔여물·외장스토리지는 발견되지 않았다.",
        "라운지 좌석 3번에 헤드폰 케이스와 빈 커피컵이 남아 있었고, 좌석 배정표상 이대리 사용 빈도가 높다. 지문 채취는 진행 중이다.",
    ]
    cctv_out = _pad_to(cctv, 800, cctv_pads) + "\n"
    scene_out = _pad_to(scene, 800, scene_pads) + "\n"
    (RAW / "forensics" / "cctv_hallway.md").write_text(cctv_out, encoding="utf-8")
    (RAW / "forensics" / "scene_intake.md").write_text(scene_out, encoding="utf-8")
    print(f"  forensics/cctv_hallway.md: {len(cctv_out.strip())} chars")
    print(f"  forensics/scene_intake.md: {len(scene_out.strip())} chars")


def write_messenger(n_dense: int = 2200, n_noise: int = 2000) -> None:
    """사건±1주 밀도 + 나머지 노이즈 → 총 ~4200줄."""
    path = RAW / "messenger" / "slack_archive.jsonl"
    start = datetime(2026, 7, 1, 9, 0, 0)
    incident = datetime(2026, 7, 29, 0, 0, 0)
    lines: list[str] = []

    # 7/1 ~ 7/21 노이즈 (성김)
    t = start
    while t < datetime(2026, 7, 22) and len(lines) < n_noise // 2:
        if RNG.random() < 0.15:
            a, b = RNG.sample([e[1] for e in EMPLOYEES], 2)
            msg = {
                "ts": t.strftime("%Y-%m-%dT%H:%M:%S+09:00"),
                "from": a,
                "to": b,
                "channel": "random",
                "text": RNG.choice(NOISE_CHAT),
            }
            lines.append(json.dumps(msg, ensure_ascii=False))
        t += timedelta(minutes=RNG.randint(20, 180))

    # 7/22 ~ 8/5 밀도 (사건 전후)
    t = datetime(2026, 7, 22, 8, 0, 0)
    dense_end = datetime(2026, 8, 5, 22, 0, 0)
    while t < dense_end and len(lines) < (n_noise // 2 + n_dense):
        a, b = RNG.sample([e[1] for e in EMPLOYEES], 2)
        text = RNG.choice(NOISE_CHAT)
        if t.date() == incident.date() and t.hour == 22:
            text = RNG.choice(["오늘 야근 길어지겠다", "오메가 체크포인트 떴다", "서버실 에어컨 요란하다"])
        msg = {
            "ts": t.strftime("%Y-%m-%dT%H:%M:%S+09:00"),
            "from": a,
            "to": b,
            "channel": RNG.choice(["general", "omega-ops", "random", "dm"]),
            "text": text,
        }
        lines.append(json.dumps(msg, ensure_ascii=False))
        t += timedelta(minutes=RNG.randint(1, 12))

    # Smoking gun DM (시간 루프와 무관하게 고정 삽입)
    lines.insert(
        min(len(lines), 2500),
        json.dumps(
            {
                "ts": "2026-07-29T23:20:11+09:00",
                "from": "박신입",
                "to": "윤사원",
                "channel": "dm",
                "text": "야 나 지금 팀장 몰래 서버실 들어왔어... 누군가 또 들어온 것 같기도 하고 ㄷㄷ",
                "evidence_id": "ev_msg_12",
            },
            ensure_ascii=False,
        ),
    )
    lines.insert(
        min(len(lines), 2501),
        json.dumps(
            {
                "ts": "2026-07-29T23:21:03+09:00",
                "from": "윤사원",
                "to": "박신입",
                "channel": "dm",
                "text": "지금 화장실이라며? 위험하니까 그냥 나와.",
            },
            ensure_ascii=False,
        ),
    )

    # 패딩 to ~4000
    while len(lines) < 4000:
        t += timedelta(minutes=RNG.randint(5, 60))
        a, b = RNG.sample([e[1] for e in EMPLOYEES], 2)
        lines.append(
            json.dumps(
                {
                    "ts": t.strftime("%Y-%m-%dT%H:%M:%S+09:00"),
                    "from": a,
                    "to": b,
                    "channel": "random",
                    "text": RNG.choice(NOISE_CHAT),
                },
                ensure_ascii=False,
            )
        )

    path.write_text("\n".join(lines) + "\n", encoding="utf-8")
    print(f"  messenger/slack_archive.jsonl: {len(lines)} lines, {path.stat().st_size // 1024} KB")


def write_access_logs(n_lines: int = 15000) -> None:
    path = RAW / "logs" / "access_control.txt"
    doors = ["lobby", "office_floor3", "lounge", "server_room", "parking", "lab"]
    actions = ["ENTER", "EXIT", "DENIED", "PING"]
    start = datetime(2026, 7, 28, 0, 0, 0)
    lines: list[str] = [
        "# access control bulk log — generated",
        "# timezone: Asia/Seoul",
    ]
    t = start
    smoking_written = False
    while len(lines) < n_lines:
        emp = RNG.choice(EMPLOYEES)
        door = RNG.choice(doors)
        action = RNG.choice(actions if door != "server_room" else ["ENTER", "EXIT", "DENIED"])
        auth = "badge"
        # plant smoking gun near target time
        if (
            not smoking_written
            and t >= datetime(2026, 7, 29, 23, 10, 0)
            and t <= datetime(2026, 7, 29, 23, 11, 0)
        ):
            lines.append(
                "2026-07-29T23:10:33+09:00 badge=E-A name=김팀장 auth=fingerprint "
                "door=server_room ACTION=ENTER  # evidence_id: ev_log_07"
            )
            smoking_written = True
            t += timedelta(seconds=30)
            continue
        # realistic night sparse
        if t.hour >= 23 or t.hour < 6:
            if RNG.random() > 0.3:
                t += timedelta(seconds=RNG.randint(20, 90))
                continue
        line = (
            f"{t.strftime('%Y-%m-%dT%H:%M:%S+09:00')} badge={emp[0]} name={emp[1]} "
            f"auth={auth} door={door} ACTION={action}"
        )
        lines.append(line)
        t += timedelta(seconds=RNG.randint(5, 45))
        if t > datetime(2026, 7, 31, 23, 59, 0):
            t = start + timedelta(minutes=RNG.randint(0, 1000))

    if not smoking_written:
        lines.insert(100, (
            "2026-07-29T23:10:33+09:00 badge=E-A name=김팀장 auth=fingerprint "
            "door=server_room ACTION=ENTER  # evidence_id: ev_log_07"
        ))

    path.write_text("\n".join(lines[:n_lines]) + "\n", encoding="utf-8")
    print(f"  logs/access_control.txt: {min(len(lines), n_lines)} lines, {path.stat().st_size // 1024} KB")


def write_corporate_card(n_rows: int = 800) -> None:
    path = RAW / "corporate_card" / "transactions.csv"
    merchants = [
        "구내식당",
        "편의점",
        "카페",
        "택시",
        "문구점",
        "전자상가",
        "마라탕집",
        "배달앱",
        "강남역 룸살롱",
        "주유소",
    ]
    start = datetime(2026, 5, 1, 12, 0, 0)
    rows: list[dict[str, str]] = []
    t = start
    smoking = False
    while len(rows) < n_rows:
        emp = RNG.choice(EMPLOYEES)
        merchant = RNG.choice(merchants[:-1])  # avoid salon except plant
        amount = RNG.randint(3000, 85000)
        note = "일반"
        if (
            not smoking
            and t.date() >= datetime(2026, 7, 29).date()
            and len(rows) > n_rows // 2
        ):
            rows.append(
                {
                    "datetime": "2026-07-29 23:30:00",
                    "holder": "김팀장",
                    "employee_id": "E-A",
                    "merchant": "강남역 룸살롱",
                    "amount_krw": "850000",
                    "note": "심야 접대 결제 evidence_id: ev_card_03",
                }
            )
            smoking = True
            continue
        rows.append(
            {
                "datetime": t.strftime("%Y-%m-%d %H:%M:%S"),
                "holder": emp[1],
                "employee_id": emp[0],
                "merchant": merchant,
                "amount_krw": str(amount),
                "note": note,
            }
        )
        t += timedelta(hours=RNG.randint(1, 14), minutes=RNG.randint(0, 59))
        if t > datetime(2026, 7, 31, 23, 0, 0):
            t = start + timedelta(days=RNG.randint(0, 40))

    if not smoking:
        rows.append(
            {
                "datetime": "2026-07-29 23:30:00",
                "holder": "김팀장",
                "employee_id": "E-A",
                "merchant": "강남역 룸살롱",
                "amount_krw": "850000",
                "note": "심야 접대 결제 evidence_id: ev_card_03",
            }
        )

    with path.open("w", encoding="utf-8", newline="") as f:
        w = csv.DictWriter(
            f,
            fieldnames=["datetime", "holder", "employee_id", "merchant", "amount_krw", "note"],
        )
        w.writeheader()
        w.writerows(rows[:n_rows])
    print(f"  corporate_card/transactions.csv: {min(len(rows), n_rows)} rows, {path.stat().st_size // 1024} KB")


def write_network(n_extra: int = 2000) -> None:
    path = RAW / "network" / "wifi_transfer_log.txt"
    lines = [
        "# internal wifi / network transfer log",
        "# facility: office floor3 lounge AP",
        "2026-07-29T23:05:12+09:00 event=ASSOC ip=192.168.1.15 mac=AA:BB:CC:11:22:33 ap=lounge-ap-01 note=device=이대리_개인노트북",
        "2026-07-29T23:08:44+09:00 event=DNS q=netflix.com ip=192.168.1.15",
        "2026-07-29T23:25:06+09:00 event=BULK_TRANSFER ip=192.168.1.15 mac=AA:BB:CC:11:22:33 ap=lounge-ap-01 "
        "bytes=107374182400 proto=HTTPS dest=ext-unknown direction=EGRESS status=COMPLETE  # evidence_id: ev_net_01",
        "2026-07-29T23:25:07+09:00 event=ALERT rule=DATA_EXFIL_THRESHOLD msg=\"~100GB packet external transfer complete\"",
    ]
    t = datetime(2026, 7, 28, 0, 0, 0)
    for _ in range(n_extra):
        emp = RNG.choice(EMPLOYEES)
        ip = f"192.168.1.{RNG.randint(2, 254)}"
        mac = f"AA:BB:CC:{RNG.randint(0,255):02X}:{RNG.randint(0,255):02X}:{RNG.randint(0,255):02X}"
        ev = RNG.choice(["ASSOC", "DNS", "HTTP", "DHCP", "DISC"])
        lines.append(
            f"{t.strftime('%Y-%m-%dT%H:%M:%S+09:00')} event={ev} ip={ip} mac={mac} "
            f"user={emp[1]} ap=lounge-ap-0{RNG.randint(1,3)} bytes={RNG.randint(64, 5000000)}"
        )
        t += timedelta(seconds=RNG.randint(10, 120))
    path.write_text("\n".join(lines) + "\n", encoding="utf-8")
    print(f"  network/wifi_transfer_log.txt: {len(lines)} lines, {path.stat().st_size // 1024} KB")


def main() -> None:
    print("[generate_rag_dataset] building corpus…")
    reset_raw()
    write_statements()
    write_forensics()
    write_messenger()
    write_access_logs()
    write_corporate_card()
    write_network()
    print("[generate_rag_dataset] done → data/raw/")
    print("Next: python3 ingest.py && python3 build_index.py")


if __name__ == "__main__":
    main()
