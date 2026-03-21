import pandas as pd
import matplotlib.pyplot as plt

def run_comparison():
    rag_service = RagService()
    
    # 第一次：跑关闭 Rerank 的版本
    scores_no_rerank = evaluate_your_rag(rag_service, use_rerank=False)
    
    # 第二次：跑开启 Rerank 的版本
    scores_with_rerank = evaluate_your_rag(rag_service, use_rerank=True)
    
    # 绘制对比雷达图（Radar Chart）
    plot_comparison(scores_no_rerank, scores_with_rerank)

def plot_comparison(s1, s2):
    # 这里可以用 matplotlib 画一个简单的条形图对比
    labels = ['Faithfulness', 'Answer Relevance', 'Context Precision']
    # 假设 s1 和 s2 是得分列表
    # ... 绘图代码 ...
    plt.show()