import os
from datasets import Dataset
from ragas import evaluate
from ragas.metrics import faithfulness, answer_relevance, context_precision, context_recall
from rag.py import RagService  # 导入你的服务类

# 1. 准备测试集 (Ground Truth 是你认为的正确标准答案)
test_questions = [
    {
        "question": "阿尔吉侬最后怎么了？",
        "ground_truth": "它死了，被放入小小的棺材里埋在查理的后院。"
    },
    {
        "question": "查理的手术提升了他的智力吗？",
        "ground_truth": "是的，手术后他的智力顺利突破了实验室测定的智商标准。"
    }
]

def run_evaluation():
    rag_service = RagService()
    results = []

    print("开始生成测试数据...")
    for item in test_questions:
        # 调用你现有的 ask 方法
        # 注意：需要模拟一个 session_id
        response = rag_service.ask(item["question"], {"session_id": "eval_test_001"})
        
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
    # Ragas 默认需要调用 OpenAI，如果你想用通义千问作为评判员，需要额外配置 llm
    print("正在调用 LLM 进行自动评分...")
    score = evaluate(
        dataset,
        metrics=[
            faithfulness,        # 忠实度：回答是否源于 context
            answer_relevance,   # 相关性：回答是否跑题
            context_precision,  # 检索精度：搜到的东西是否有用
        ]
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