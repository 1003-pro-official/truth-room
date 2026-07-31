# notebooks/

Colab 실험용 자리. **정본 로직은 루트 `.py` + `configs/*.yaml`** 입니다.

권장:

```bash
python3 ingest.py
python3 build_index.py
python3 rag_pipeline.py --mode advanced
python3 agent_graph.py --smoke                 # LangGraph StateGraph
python3 scripts/smoke_autogen_ask.py           # AutoGen ask (OPENAI_API_KEY)
python3 evaluate.py
python3 scripts/eval_ragas.py                  # RAGAS · Python ≥3.10 · n=30
python3 scripts/plot_metrics.py                # → report/assets/
```
