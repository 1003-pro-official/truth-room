# 방구석 프로파일러: 진실의 방으로 — 레퍼런스 (References)

> **역할:** 아이디어·실현 근거·논문·채택 OSS의 **탐색 지도**.  
> **에이전트 지침:** 구현 전 본 문서를 읽고, [CLAUDE.md](CLAUDE.md) §0.5·[AI_CONVENTION.md](AI_CONVENTION.md)와 함께 적용.  
> 핵심 파이프라인은 **이미 구현됨** — 범위 안에서 확장·고도화. UI→LLM 직결·YOLO/CV는 비범위. AutoGen은 심문 턴 본선(`lib/autogen_runtime.py`).

---

## 1. 채택 OSS · 스택 요약 (Phase 매핑)

| ID | 기술 | 용도 | Phase | 공식 문서 / 참조 |
| :--- | :--- | :--- | :--- | :--- |
| S1 | **Hybrid RAG** (`lib/rag_core.py`) | 증거 검색 · Baseline/Advanced | **1b** | Gao et al. RAG Survey · Modular RAG |
| S2 | **LangGraph** (`lib/langgraph_runtime.py` · `agent_graph.py`) | 심문·압박·상태 분기 (공식 StateGraph) | **1c** | [LangGraph Docs](https://langchain-ai.github.io/langgraph/) |
| S2b | **AutoGen** (`lib/autogen_runtime.py`) | ask 턴 GroupChat (용의자·조수·심판) | **1c/2** | [microsoft/autogen](https://github.com/microsoft/autogen) · round_robin · max_round |
| S3 | **Function Calling** (`lib/tools.py`) | CCTV·포렌식 툴 | **1c** | OpenAI / 로컬 툴 스키마 |
| S4 | **FastAPI** | Session · ask · search · tool · accuse | **2** | [fastapi.tiangolo.com](https://fastapi.tiangolo.com/) |
| S5 | **Streamlit** | 심문 UI (`st.chat_message` 등) · **API only** | **3** | [Streamlit chat](https://docs.streamlit.io/develop/api-reference/chat) |
| S6 | **notion-client** | README → Notion 리포트 | 공통 | [developers.notion.com](https://developers.notion.com/) |

**비채택(범위 밖):** 무제한 AutoGen 티키타카(상한·폴백 없는) · YOLO/CV · UI에서 LLM 직결

---

## 2. 참고자료 및 인용자료

### 2.1 아이디어 제안에 도움이 된 소스

#### PyTorch KR — Oh My Opencode Subagent

- **링크:** [discuss.pytorch.kr — Oh My Opencode Subagent](https://discuss.pytorch.kr/t/oh-my-opencode-subagent-opencode-all-in-one/8586)
- **참고 내용:** 대규모 작업을 쪼개 전담하는 Subagent 구조·올인원 에이전트 프레임워크 트렌드를 참고해, 본 프로젝트는 **조력 AI(GM/탐정 툴)** 와 **용의자 AI(페르소나)** 를 역할 분리로 설계했다.

#### Character.ai · 뤼튼(Wrtn) 서비스 분석

- **참고 내용:** 시장에서 흥행하는 **페르소나 기반 캐릭터 채팅**의 몰입감을 차용하되, 기존 서비스의 「목적성 부재」 한계를 **방탈출형 규칙(증거 수집·압박·지목)** 으로 보완한다.

---

### 2.2 실현 방안의 근거

#### LangGraph — Stateful Graph Architecture

- **문서:** [LangGraph](https://langchain-ai.github.io/langgraph/)
- **근거:** 일반 DAG(단방향)가 아닌 **순환(Cyclic) 그래프**를 지원해, 게임 내내 용의자 **스트레스(pressure)** · 플레이어 **증거 수집 상태**를 메모리에 유지하고 자백/부인 분기를 제어할 수 있는 기술적 근거가 된다.  
  *(구현: `lib/langgraph_runtime.py` 공식 StateGraph · 노드 로직 `agent_graph.py` · 미설치 시 순차 폴백. ask 본선은 AutoGen.)*

#### Streamlit Conversational UI

- **문서:** `st.chat_message` · `st.dataframe` — [Streamlit Chat](https://docs.streamlit.io/develop/api-reference/chat)
- **근거:** React 등 무거운 프론트 없이 **심문 채팅창**과 **CSV·로그형 증거**를 한 화면에 인터랙티브하게 렌더링할 수 있음을 확인.

#### Modular RAG (라우팅 메커니즘)

- **근거:** 사용자 질문 의도(예: 「어제 법인카드 어디서 긁었어?」)를 LLM/라우터가 이해한 뒤, **텍스트 코퍼스(대화·진술)** 와 **구조화 데이터(결제 CSV·출입·네트워크 로그)** 를 동적으로 선택·검색하는 Advanced RAG의 실현 가능성을 확인.

---

### 2.3 진행 시 참고할 논문

#### 논문 1 — Generative Agents: Interactive Simulacra of Human Behavior

- **저자·연도:** Park et al., 2023 (Stanford)
- **활용 방안:** 성격이 다른 용의자 3인(권위적·완벽주의·신입)에 **페르소나·단기/장기 기억**을 부여하고, 정교한 프롬프트를 설계할 때 행동 가이드로 참고.

#### 논문 2 — Retrieval-Augmented Generation for Large Language Models: A Survey

- **저자·연도:** Gao et al., 2023
- **활용 방안:** 위조·다형 증거(로그·영수증·대화)에서 정확한 단서만 교차검증·추출하기 위한 **Advanced RAG**(Query Routing · Retriever 튜닝) 파이프라인 최적화 참고.  
  본 프로젝트 대응: Baseline(dense) vs Advanced(hybrid RRF + rerank) · Faithfulness 평가.

---

## 3. 영역별 구현 매핑 (본 레포)

| 레퍼런스 개념 | 레포 경로 | 상태 |
| :--- | :--- | :---: |
| 조력 AI / 용의자 AI 분리 | `data/personas/` · `lib/autogen_runtime.py` · GM 톤 | 🟢 |
| 방탈출형 규칙 · win_condition | `data/scenarios/case_01.yaml` | 🟢 |
| Modular / Hybrid RAG | `lib/rag_core.py` · soft routing · Hit@5 4/4 · C-Prec 0.40 | 🟢 |
| Stateful 압박 루프 | `lib/langgraph_runtime.py` · `agent_graph.py` | 🟢 LangGraph smoke |
| AutoGen GroupChat ask | `lib/autogen_runtime.py` | 🟢 본선 |
| Streamlit 심문 UI | `app.py` → FastAPI only | 🟢 |
| RAGAS · 메트릭 그래프 | `scripts/eval_ragas.py` · `scripts/plot_metrics.py` · `report/assets/` | 🟢 |
| 리포트 · Notion | `update_report.py` · `update_notion.py` | 🟢 |

---

## 4. 에이전트 CLI 사용법 (프롬프트 템플릿)

행동지침 문서에 `@references.md`를 포함하면, 에이전트는 **채택 OSS·비범위·경로 매핑**을 따른다.

```text
@CLAUDE.md @AI_CONVENTION.md @references.md @TECH_SPEC.md
references.md의 Modular RAG·역할 분리 범위 안에서
기존 lib/rag_core.py · evaluate.py만 고도화하고,
뼈대 재작성·UI→LLM 직결·무제한 AutoGen은 넣지 마. 심문 AutoGen은 `lib/autogen_runtime.py`만.
```

```text
@CLAUDE.md @references.md @data/personas/
Generative Agents 논문 관점으로 suspect_b 페르소나 프롬프트만 강화해 줘.
culprit_id는 클라이언트 응답에 넣지 마.
```
---

## 5. 관련 문서

| 문서 | 용도 |
| :--- | :--- |
| [TECH_SPEC.md](TECH_SPEC.md) | 스택·스키마 정본 |
| [MASTER_PLAN.md](MASTER_PLAN.md) | 제품·골든 루트 |
| [ARCHITECTURE.md](ARCHITECTURE.md) | 팀 OS · 파이프라인 |
| [README.md](README.md) | 결과 리포트 |
| [GETTING_STARTED.md](GETTING_STARTED.md) | 실행 |
