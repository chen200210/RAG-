import os
from datasets import Dataset
from ragas import evaluate
try:
    from ragas.metrics.collections import (
        faithfulness,
        answer_relevance,
        context_precision,
        context_recall,
    )
except Exception:
    from ragas.metrics import faithfulness, context_precision, context_recall

    try:
        from ragas.metrics import answer_relevance
    except Exception:
        from ragas.metrics._answer_relevance import answer_relevancy as answer_relevance

from rag import RagService
import config_data as config

def _build_ragas_llm_and_embeddings():
    try:
        from langchain_community.chat_models.tongyi import ChatTongyi
        from ragas.llms import LangchainLLMWrapper
        from ragas.embeddings import LangchainEmbeddingsWrapper
    except Exception:
        return None, None

    llm = LangchainLLMWrapper(ChatTongyi(model=config.chat_model, temperature=0.0))
    embeddings = LangchainEmbeddingsWrapper(config.embedding_function)
    return llm, embeddings

# 1. 准备测试集 (Ground Truth 是你认为的正确标准答案)
test_questions = [
    {
        "question": "第一、二、三空间的人口数量分别是多少？",
        "category": "基础事实提取",
        "ground_truth": "第一空间人口500万，第二空间人口2500万，第三空间人口5000万。"
    },
    {
        "question": "三个空间在48小时的周期内，分别占用多少小时的时间？",
        "category": "跨段落数值聚合",
        "ground_truth": "第一空间从第一天早晨六点到第二天早晨六点（24小时）；第二空间从第二天早晨六点到晚上十点（16小时）；第三空间从第二天晚上十点到第三天早晨六点（8小时）。"
    },
    {
        "question": "老葛为什么反对在第三空间使用全自动化的垃圾处理技术？",
        "category": "因果逻辑推断",
        "ground_truth": "因为老葛认为自动化技术会取代人工分拣，导致第三空间数千万依赖此维持生计的垃圾工彻底失业，失去生存来源。"
    },
    {
        "question": "文中提到的‘折叠’动作通常在什么时间点发生？",
        "category": "细节定位",
        "ground_truth": "折叠通常在空间转换的时间节点发生，例如清晨六点，整座城市会进行翻转和折叠。"
    },
    {
        "question": "老陆（第一空间）对垃圾处理的看法与老葛有什么本质不同？",
        "category": "多对象观点对比",
        "ground_truth": "老陆从能源转化和宏观成本角度看，认为技术升级是必然；老葛从社会底层生存角度看，认为技术升级是对穷人生存权的剥夺。"
    },
    {
        "question": "根据文档，第一空间的人是否知道第三空间的人的存在？",
        "category": "隐含关系推断",
        "ground_truth": "是的，第一空间的人知道，但他们通常选择忽视，或者将其视为维持城市运转的必要‘底层细节’。"
    }
]

def run_evaluation():
    rag_service = RagService()
    results = []

    print("开始生成测试数据...")
    for item in test_questions:
        # 调用你现有的 ask 方法
        # 注意：需要模拟一个 session_id
        response = rag_service.ask_sync(item["question"], {"session_id": "eval_test_001"})
        
        # 构造 Ragas 需要的数据格式
        results.append({
            "question": item["question"],
            "answer": response["answer"],
            "contexts": [doc.page_content for doc in response["context"]],
            "ground_truth": item["ground_truth"]
        })

    # 2. 转换为 Dataset 对象
    dataset = Dataset.from_list(results)

    # 3. 执行评估
    print("正在调用 LLM 进行自动评分...")
    llm, embeddings = _build_ragas_llm_and_embeddings()
    score = evaluate(
        dataset,
        metrics=[
            faithfulness,        # 忠实度：回答是否源于 context
            answer_relevance,   # 相关性：回答是否跑题
            context_precision,  # 检索精度：搜到的东西是否有用
        ],
        llm=llm,
        embeddings=embeddings,
    )

    # 4. 输出结果
    print("\n--- 评估结果 ---")
    df = score.to_pandas()
    print(df)
    
    # 保存结果到 CSV，方便写论文/汇报
    df.to_csv("rag_eval_results.csv", index=False)
    print("\n结果已保存至 rag_eval_results.csv")

if __name__ == "__main__":
    run_evaluation()
