# Langfuse 관측 게시판

> **목적:** 심문 ask 턴의 Input/Output·세션을 **게임 안 게시판 레이어**로 보여주고, 선택적으로 Langfuse 클라우드에 동기화한다.  
> **정본 UI 설명:** [README.md §5](../README.md) · **스펙:** [TECH_SPEC.md](../TECH_SPEC.md) §4.2

관련 구현: `lib/langfuse_obs.py` · `backend/main.py` · `web/game` 사이드바「관측 (Langfuse)」

---

## 1. 흐름

```
ask 성공
  → 로컬 링버퍼 (세션별)
  → (키 있으면) Langfuse ingestion
게임 UI「관측」
  → 전체 화면 보드 (팝업 아님)
  → Tracing 탭 / Sessions 탭(아코디언)
```

| 탭 | 내용 |
| :--- | :--- |
| **Tracing** | 프로젝트 최근 ask trace 표 (Start · Name · Input · Output · Session) |
| **Sessions** | 세션 목록 FAQ 펼침 → 해당 세션 Input/Output 카드 |

모바일(≤900px): PC 확인 안내만 표시.

---

## 2. 설정

`.env` 또는 Railway Variables:

```bash
LANGFUSE_PUBLIC_KEY=pk-lf-...
LANGFUSE_SECRET_KEY=sk-lf-...
LANGFUSE_BASE_URL=https://us.cloud.langfuse.com   # 리전에 맞게
# 선택
LANGFUSE_PROJECT_ID=...   # 없으면 /api/public/projects 조회
```

키가 없으면 **local only**(서버 버퍼). 시크릿은 클라이언트에 내려가지 않음.

---

## 3. API (시크릿 미노출)

| Method | Path | 역할 |
| :--- | :--- | :--- |
| `GET` | `/api/v1/observability/status` | 설정 여부 |
| `GET` | `/api/v1/session/{id}/observability` | Tracing + Sessions 요약 |
| `GET` | `/api/v1/observability/sessions/{id}` | 세션 아코디언용 상세 |

---

## 4. 배포 메모

- 코드 배포만으로는 부족 → Railway Variables에 `LANGFUSE_*` 등록
- 보드 **Open in Langfuse** → 클라우드 Tracing/Sessions 목록
- ask 직후 클라우드 반영이 늦을 수 있음 → 보드 로컬 버퍼로 즉시 시연 가능
