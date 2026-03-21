# src/analysis/llm_analyzer.py

import os
import json
from typing import List, Optional

# 导入必要的库
# Pydantic 用于数据模型定义和验证
from pydantic import BaseModel, Field, ValidationError
# Tenacity 用于实现 API 请求的自动重试
from tenacity import retry, stop_after_attempt, wait_random_exponential
# OpenAI 客户端库
from openai import OpenAI


# --- 1. 定义 Pydantic 数据模型，用于结构化输出 ---
# 这个模型强制规定了 LLM 返回的 JSON 格式，确保了输出的稳定性和可预测性。

class AnalysisResult(BaseModel):
    """
    简历与JD分析结果的数据模型
    """
    overall_match_score: int = Field(
        ...,
        description="综合匹配度评分，范围从0到100的整数。",
        ge=0,
        le=100
    )
    matched_skills: List[str] = Field(
        ...,
        description="简历与JD高度匹配的技能或经历列表。这些是求职者的核心优势。"
    )
    missing_skills: List[str] = Field(
        ...,
        description="JD中要求但简历中缺失或薄弱的关键技能列表。"
    )
    resume_optimization_advice: str = Field(
        ...,
        description="针对电子工程和算法方向，提出的具体简历修改建议，例如如何量化项目成果、如何重写项目描述以突出与岗位的关联性。"
    )
    study_path: str = Field(
        ...,
        description="针对'missing_skills'中列出的技能，给出的具体、可执行的短期学习路径建议，例如推荐的课程、开源项目或实践方法。"
    )


# --- 2. 设计高质量的 System Prompt ---
# 这个 Prompt 是整个分析模块的“灵魂”，它指导大模型如何进行深度、专业的分析。

SYSTEM_PROMPT = """
你是一位顶级的AI算法岗位招聘专家，同时拥有深厚的电子工程背景知识。你的任务是深度分析一份求职者的简历和一份机器学习/算法实习岗位的职位描述（JD），并提供结构化的、富有洞察力的分析报告。

你的分析必须遵循以下原则：
1.  **超越关键词匹配**：不要仅仅进行表面的词语匹配。你需要理解技术背后的核心能力。例如，如果简历中提到了“数字信号处理(DSP)”项目，而JD要求“时间序列分析”，你应该能识别出两者在信号处理和模式识别上的共通之处，并将其视为一种潜在的匹配。
2.  **评估可迁移能力**：对于电子工程背景的求职者，要特别关注其在数学、物理、信号系统、控制理论等基础学科中展现的抽象建模和系统分析能力，并评估这些能力迁移到机器学习领域的潜力。
3.  **结果必须结构化**：你的输出必须是一个严格的JSON对象，不能包含任何额外的解释性文字。JSON的结构必须严格遵守我提供的格式。
4.  **建议必须具体可行**：提供的简历修改建议和学习路径必须是具体、可执行的，而不是空泛的套话。例如，指出简历中某个项目应该如何用STAR法则来重写，或者推荐某个具体的GitHub项目来练习缺失的技能。
"""


# --- 3. 实现核心分析类 ResumeAnalyzer ---

class ResumeAnalyzer:
    """
    使用大语言模型（LLM）API来分析简历和职位描述（JD）的匹配度。
    """

    def __init__(self, api_key: Optional[str] = None, base_url: Optional[str] = None):
        """
        初始化分析器。

        Args:
            api_key (Optional[str]): 用于API调用的密钥。如果为None，则会尝试从环境变量 'OPENAI_API_KEY' 中读取。
            base_url (Optional[str]): API的基地址。用于适配兼容OpenAI接口的其他服务（如DeepSeek, Kimi等）。
                                      如果为None，则使用OpenAI官方地址。
        """
        self.api_key = api_key or os.getenv("OPENAI_API_KEY")
        

        
        if not self.api_key:
            raise ValueError("API key is not provided. Please set the OPENAI_API_KEY environment variable or pass it directly.")
        
        # 初始化 OpenAI 客户端，可以灵活指定 base_url
        self.client = OpenAI(api_key=self.api_key, base_url=base_url)

    @retry(
        wait=wait_random_exponential(min=1, max=60),
        stop=stop_after_attempt(3),
        reraise=True  # 重试失败后，重新抛出最后的异常
    )
    def analyze(self, resume_text: str, jd_text: str) -> AnalysisResult:
        """
        调用大模型API进行分析，并返回结构化的结果。

        Args:
            resume_text (str): 求职者的简历全文。
            jd_text (str): 招聘岗位的职位描述（JD）全文。

        Returns:
            AnalysisResult: 一个包含所有分析结果的 Pydantic 对象。
        
        Raises:
            ValueError: 如果API返回的数据无法解析或验证失败。
            openai.APIError: 如果API调用失败。
        """
        user_prompt = f"""
        请根据你的角色设定，深度分析以下简历和职位描述。

        --- 简历开始 ---
        {resume_text}
        --- 简历结束 ---

        --- 职位描述(JD)开始 ---
        {jd_text}
        --- 职位描述(JD)结束 ---

        请严格按照预定义的JSON格式输出你的分析报告。
        """

        try:
            response = self.client.chat.completions.create(
                model="qwen-plus",  # 您可以替换为其他兼容模型，如 deepseek-chat
                messages=[
                    {"role": "system", "content": SYSTEM_PROMPT},
                    {"role": "user", "content": user_prompt},
                ],
                # 使用 'tools' 和 'tool_choice' 来强制模型输出指定的JSON结构
                tools=[{"type": "function", "function": {"name": "analysis_output", "parameters": AnalysisResult.model_json_schema()}}],
                tool_choice={"type": "function", "function": {"name": "analysis_output"}},
                temperature=0.2,  # 较低的温度确保输出的稳定性和一致性
            )

            # 提取模型返回的JSON字符串
            tool_calls = response.choices[0].message.tool_calls
            if not tool_calls:
                raise ValueError("API response did not contain the expected tool calls.")
            
            result_json_str = tool_calls[0].function.arguments
            
            # 解析并使用Pydantic模型进行验证
            analysis_result = AnalysisResult.model_validate_json(result_json_str)
            return analysis_result

        except (json.JSONDecodeError, ValidationError) as e:
            print(f"数据解析或验证失败: {e}")
            print(f"原始返回内容: {result_json_str if 'result_json_str' in locals() else 'N/A'}")
            raise ValueError("API返回的数据格式不正确，无法解析。") from e
        except Exception as e:
            print(f"API调用时发生未知错误: {e}")
            raise


# --- 4. 测试入口 ---
if __name__ == "__main__":
    # 这是一个示例，演示如何使用 ResumeAnalyzer 类。
    # 在实际运行前，请确保您已经设置了环境变量 `OPENAI_API_KEY`。
    # 例如: export OPENAI_API_KEY='your_api_key'
    
    # 模拟的简历文本 (电子工程背景，有机器学习项目)
    mock_resume = """
    张三 | 电子工程硕士
    
    教育背景：
    - XX大学，电子与计算机工程，硕士 (2023-2026)
    - YY大学，电子信息工程，学士 (2019-2023)
    
    技能栈：
    - 编程语言: Python (精通), C++, MATLAB
    - 机器学习: PyTorch, Scikit-learn, TensorFlow, Numpy, Pandas
    - 硬件相关: Verilog, FPGA, 数字信号处理(DSP)
    
    项目经历：
    1. 基于FPGA的实时图像边缘检测系统 (毕业设计)
       - 使用Verilog在FPGA上实现Sobel算子，对摄像头采集的视频流进行实时边缘检测。
       - 负责算法的硬件实现与优化，通过流水线技术将处理速度提升了3倍。
    
    2. 基于PyTorch的音频分类器 (课程项目)
       - 使用MFCC提取音频特征，搭建了一个卷积神经网络（CNN）对城市噪音进行分类。
       - 最终在UrbanSound8K数据集上达到了85%的准确率。
       - 独立完成了数据预处理、模型搭建、训练和评估的全过程。
    """

    # 模拟的职位描述 (JD)
    mock_jd = """
    算法实习生 (机器学习方向)
    
    工作职责：
    1. 参与前沿机器学习算法在推荐系统中的研发与实现。
    2. 负责数据清洗、特征工程、模型训练与评估等环节。
    3. 跟踪最新的深度学习技术，并将其应用于实际业务场景。
    
    任职要求：
    1. 计算机、电子信息、自动化等相关专业，硕士及以上学历。
    2. 熟悉至少一种深度学习框架（PyTorch/TensorFlow），并有实际项目经验。
    3. 具备扎实的编程基础（Python优先），熟悉常见的数据结构和算法。
    4. 对时间序列分析、强化学习或推荐系统有了解者优先。
    5. 具备良好的逻辑思维能力和团队协作精神。
    """

    print("正在初始化简历分析器...")
    try:
        # 如果您使用兼容OpenAI的第三方服务，可以这样初始化：
        analyzer = ResumeAnalyzer(
            api_key=os.getenv("OPENAI_API_KEY"),
            base_url="https://dashscope.aliyuncs.com/compatible-mode/v1"
        )
        
        print("正在调用API进行分析，请稍候...")
        analysis_report = analyzer.analyze(mock_resume, mock_jd)
        
        print("\n--- 简历与JD分析报告 ---")
        print(f"\n[+] 综合匹配度: {analysis_report.overall_match_score}/100")
        
        print("\n[+] 高度匹配的技能/经历:")
        for skill in analysis_report.matched_skills:
            print(f"  - {skill}")
            
        print("\n[-] 缺失或薄弱的技能:")
        for skill in analysis_report.missing_skills:
            print(f"  - {skill}")
            
        print("\n[+] 简历优化建议:")
        print(f"  {analysis_report.resume_optimization_advice.replace('。', '。\n  ')}")
        
        print("\n[+] 学习路径建议:")
        print(f"  {analysis_report.study_path.replace('。', '。\n  ')}")

    except ValueError as e:
        print(f"\n错误: {e}")
    except Exception as e:
        print(f"\n发生了一个未预料到的错误: {e}")
