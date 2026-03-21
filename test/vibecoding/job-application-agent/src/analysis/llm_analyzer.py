import os
import json
from typing import List, Optional

from pydantic import BaseModel, Field, ValidationError
from tenacity import retry, stop_after_attempt, wait_random_exponential
from openai import OpenAI

# --- 1. 重新设计 Pydantic 数据模型 ---

class MatchedHighlight(BaseModel):
    """
    用于描述单个高度匹配项的模型。
    """
    jd_requirement: str = Field(..., description="职位描述(JD)中的一项具体要求。")
    resume_evidence: str = Field(..., description="简历中能够证明满足该项要求的具体内容（如项目经历、技能点等）。")

class AnalysisResult(BaseModel):
    """
    简历与JD深度分析结果的数据模型 (V2)。
    """
    overall_match_score: int = Field(
        ...,
        description="简历与JD的整体匹配度评分，范围从0到100的整数。",
        ge=0,
        le=100
    )
    # 使用新的模型来结构化地存储高亮项
    matched_highlights: List[MatchedHighlight] = Field(
        ...,
        description="一个列表，包含所有被识别为高度匹配（>80%）的JD要求及其在简历中的证据。"
    )
    missing_skills: List[str] = Field(
        ...,
        description="JD中要求但简历中缺失或薄弱的关键技能列表。"
    )
    resume_optimization_advice: str = Field(
        ...,
        description="提供一个具体的、可以落地的新项目点子来弥补技能短板，或者建议如何重写现有项目以更贴合JD。"
    )
    study_path: str = Field(
        ...,
        description="针对'missing_skills'，提供一个具体的、分步骤的短期学习路径，包括推荐的技术栈、关键库或学习资源。"
    )

# --- 2. 重新设计高质量的 System Prompt (V2) ---

SYSTEM_PROMPT_V2 = """
你是一位顶级的AI招聘架构师，专精于电子工程和机器学习领域。你的任务是进行一次极其详尽的简历-JD匹配度分析。

**核心指令:**
1.  **量化评估:** 首先，通读简历和JD，给出一个0-100的整体匹配度分数。
2.  **高亮匹配项:** 逐条分析JD中的每一项要求。如果某项要求在简历中有力地、高度匹配地被满足（满足度 > 80%），你必须将它提取出来。对于每一个提取出的高亮项，你需要同时提供“JD中的要求原文”和“简历中对应的证据”。
3.  **识别核心差距:** 明确列出JD中要求、但简历中完全缺失或非常薄弱的关键技能。
4.  **提供“可执行”的建议:**
    *   **简历优化:** 不要说空话。你需要提出一个具体的、可以添加到简历中的【新项目点子】。这个项目应该能精准地弥补核心差距。例如：“建议你做一个‘基于树莓派和摄像头的实时交通标志识别系统’项目，使用YOLOv5模型，这能同时体现你的嵌入式背景和模型部署能力。”
    *   **学习路径:** 给出具体的学习步骤。例如：“1. 学习强化学习基础（推荐Sutton的书）。2. 跟随PyTorch官方教程实现一个DQN算法。3. 在Gym环境中复现一个经典控制任务（如CartPole）。”

**输出格式:**
你的输出必须是一个严格的、没有任何多余文字的JSON对象，该对象的结构必须严格遵循我提供的Pydantic模型。
"""

class ResumeAnalyzer:
    """
    使用大语言模型（LLM）API来分析简历和职位描述（JD）的匹配度 (V2)。
    """
    def __init__(
        self,
        api_key: Optional[str] = None,
        base_url: Optional[str] = None,
        model: Optional[str] = None,
    ):
        self.api_key = api_key or os.getenv("OPENAI_API_KEY")
        if not self.api_key:
            raise ValueError("API key not provided.")
        resolved_base_url = base_url or os.getenv("OPENAI_BASE_URL")
        self.client = OpenAI(api_key=self.api_key, base_url=resolved_base_url)
        self.model = model or os.getenv("LLM_MODEL", "gpt-4o-mini")

    @retry(wait=wait_random_exponential(min=1, max=60), stop=stop_after_attempt(3), reraise=True)
    def analyze(self, resume_text: str, jd_text: str) -> Optional[AnalysisResult]:
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
                model=self.model,
                messages=[
                    {"role": "system", "content": SYSTEM_PROMPT_V2},
                    {"role": "user", "content": user_prompt},
                ],
                tools=[{"type": "function", "function": {"name": "analysis_output", "parameters": AnalysisResult.model_json_schema()}}],
                tool_choice={"type": "function", "function": {"name": "analysis_output"}},
                temperature=0.2,
            )
            tool_calls = response.choices[0].message.tool_calls
            if not tool_calls:
                raise ValueError("API response did not contain the expected tool calls.")
            
            result_json_str = tool_calls[0].function.arguments
            analysis_result = AnalysisResult.model_validate_json(result_json_str)
            return analysis_result
        except (json.JSONDecodeError, ValidationError) as e:
            print(f"数据解析或验证失败: {e}")
            return None
        except Exception as e:
            print(f"API调用时发生未知错误: {e}")
            return None

# ... (测试入口 if __name__ == "__main__": 可以保持不变或相应更新)
