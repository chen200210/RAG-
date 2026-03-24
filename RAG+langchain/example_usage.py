import os
from typing import Dict, Any
from trace_manager import get_trace_manager, trace_step


@trace_step(
    name="Retriever",
    round_from=lambda round_idx, query: round_idx,
    input_fn=lambda round_idx, query: {"query": query, "k": 5},
    output_fn=lambda docs: {"size": len(docs or []), "sources": [(d.get("source"), d.get("chunk_id")) for d in (docs or [])[:5]]},
)
def fake_retriever(round_idx: int, query: str):
    docs = [{"source": "doc.txt", "chunk_id": 1}, {"source": "doc.txt", "chunk_id": 2}]
    return docs


@trace_step(
    name="Grader",
    round_from=lambda question, context: 1,
    input_fn=lambda question, context: {"question": question[:120], "context": context[:200]},
    output_fn=lambda res: {"verdict": res.get("verdict"), "score": res.get("score"), "reason": (res.get("reason") or "")[:200]},
)
def fake_grader(question: str, context: str) -> Dict[str, Any]:
    if "人口" in question and "500万" in context:
        return {"verdict": "YES", "score": 0.98, "reason": "上下文包含明确的人口数字与空间对应关系"}
    return {"verdict": "NO", "score": 0.12, "reason": "上下文缺少人口数字或对应关系"}


@trace_step(
    name="Generator",
    round_from=lambda prompt: 1,
    input_fn=lambda prompt: {"prompt": prompt[:120]},
    output_fn=lambda res: {"answer": res.get("answer", "")[:200]},
)
def fake_generator(prompt: str) -> Dict[str, Any]:
    # 模拟一条带 usage_metadata 的返回，便于 analyzer 统计真实成本
    return {
        "answer": "第一空间人口500万，第二空间人口2500万，第三空间人口5000万。",
        "usage_metadata": {"input_tokens": 96, "output_tokens": 24, "total_tokens": 120},
    }


def main():
    tm = get_trace_manager()
    trace_id = tm.start_trace("第一、二、三空间的人口数量分别是多少？", tags={"use_rerank": True})
    docs = fake_retriever(1, "人口 500万 2500万 5000万 折叠北京")
    grade = fake_grader("第一、二、三空间的人口数量分别是多少？", "第一空间人口500万 第二空间人口2500万 第三空间人口5000万")
    gen = fake_generator("根据上下文回答人口数量问题")
    answer = gen.get("answer", "")
    tm.end_trace(answer, grade.get("verdict") == "YES", 1)
    out_dir = os.path.join("logs", "traces")
    os.makedirs(out_dir, exist_ok=True)
    tm.dump_sync(os.path.join(out_dir, f"trace_{trace_id}.json"))


if __name__ == "__main__":
    main()
