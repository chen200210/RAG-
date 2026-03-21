from typing import List
import os
from pathlib import Path

# 导入我们的核心模块
from src.analysis.llm_analyzer import ResumeAnalyzer, AnalysisResult
from src.storage.database import fetch_jobs_from_db

# --- 1. 配置路径 ---
# 使用 pathlib 优雅地处理跨平台的路径问题
PROJECT_ROOT = Path(__file__).parent
RESUME_PATH = PROJECT_ROOT / "data" / "resume" / "my_resume.md"  # 假设你的简历叫这个名字
DB_PATH = Path(os.getenv("JOB_DB_PATH", str(PROJECT_ROOT / "data" / "processed_jobs" / "jobs.db")))
REPORT_OUTPUT_PATH = PROJECT_ROOT / "analysis_report.md"

def load_resume(file_path: Path) -> str:
    """加载简历文件内容"""
    if not file_path.exists():
        raise FileNotFoundError(f"简历文件未找到: {file_path}")
    return file_path.read_text(encoding='utf-8')

def generate_markdown_report(sorted_reports: List[dict]):
    """根据分析结果生成 Markdown 报告"""
    content = ["# AI 求职分析报告\n\n"]
    content.append(f"共分析 {len(sorted_reports)} 个岗位，按匹配度从高到低排序。\n\n---\n\n")

    for report_data in sorted_reports:
        job = report_data['job']
        analysis: AnalysisResult = report_data['analysis']

        content.append(f"## 综合匹配度: {analysis.overall_match_score}% - {job['job_title']} @ {job['job_company']}\n\n")
        content.append(f"- **薪资:** {job['job_salary_range']}\n")
        content.append(f"- **经验:** {job['job_experience']}\n")
        content.append(f"- **地点:** {job['job_location']}\n\n")

        # 高亮匹配项
        content.append("### ✅ 高度匹配项\n\n")
        if analysis.matched_highlights:
            for item in analysis.matched_highlights:
                content.append(f"- **JD要求:** `{item.jd_requirement}`\n")
                content.append(f"  - **简历证据:** {item.resume_evidence}\n")
        else:
            content.append("未发现明显的高度匹配项。\n")
        content.append("\n")

        # 核心差距
        content.append("### ❌ 核心能力差距\n\n")
        if analysis.missing_skills:
            for skill in analysis.missing_skills:
                content.append(f"- {skill}\n")
        else:
            content.append("未发现明显的能力差距。\n")
        content.append("\n")

        # 定制化建议
        content.append("### 🚀 定制化提升建议\n\n")
        content.append(f"**简历优化建议:**\n\n{analysis.resume_optimization_advice}\n\n")
        content.append(f"**下一步学习路径:**\n\n{analysis.study_path}\n\n")
        content.append("---\n\n")

    REPORT_OUTPUT_PATH.write_text("".join(content), encoding='utf-8')
    print(f"\n报告已生成！请查看: {REPORT_OUTPUT_PATH}")

def main():
    """主执行函数"""
    print("--- 启动 AI 求职分析流程 ---")

    # 1. 加载简历
    try:
        resume_text = load_resume(RESUME_PATH)
        print(f"成功加载简历: {RESUME_PATH.name}")
    except FileNotFoundError as e:
        print(e)
        # 创建一个空的占位简历文件，并提示用户填充
        RESUME_PATH.parent.mkdir(exist_ok=True)
        RESUME_PATH.write_text("# 在这里粘贴您的简历内容\n\n请使用 Markdown 格式。", encoding='utf-8')
        print(f"已为您创建空的简历文件，请将您的简历内容粘贴到 {RESUME_PATH} 后重新运行。")
        return

    # 2. 从数据库加载岗位
    DB_PATH.parent.mkdir(parents=True, exist_ok=True)
    job_limit_env = os.getenv("JOB_LIMIT")
    job_limit = int(job_limit_env) if job_limit_env else None
    jobs = fetch_jobs_from_db(str(DB_PATH), limit=job_limit)
    if not jobs:
        print("未能从数据库加载任何岗位信息，请先运行爬虫项目。")
        return

    # 3. 初始化分析器
    try:
        analyzer = ResumeAnalyzer()
    except ValueError as e:
        print(f"初始化分析器失败: {e}")
        print("请确保您已设置 OPENAI_API_KEY 环境变量。")
        return

    # 4. 循环分析每个岗位
    analysis_reports = []
    for job in jobs:
        print(f"\n正在分析岗位: {job['job_title']} @ {job['job_company']}...")
        
        # 将多个字段组合成更丰富的 JD 文本
        jd_full_text = job.get("jd_text") or ""
        jd_text = f"""
        职位名称: {job['job_title']}
        工作经验: {job['job_experience']}
        学历要求: {job['job_education']}
        技能要求: {job['job_skills']}
        行业: {job['job_industry']}
        职位描述: {jd_full_text}
        """
        
        analysis_result = analyzer.analyze(resume_text, jd_text.strip())
        
        if analysis_result:
            analysis_reports.append({"job": job, "analysis": analysis_result})
            print(f"  - 分析完成，匹配度: {analysis_result.overall_match_score}%")
        else:
            print("  - 分析失败，跳过此岗位。")

    # 5. 排序并生成报告
    if analysis_reports:
        # 按匹配度从高到低排序
        sorted_reports = sorted(analysis_reports, key=lambda x: x['analysis'].overall_match_score, reverse=True)
        generate_markdown_report(sorted_reports)
    else:
        print("\n未能成功分析任何岗位，无法生成报告。")

if __name__ == "__main__":
    main()
