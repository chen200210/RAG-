from typing import List, Dict, Any

def clean_job_data(jobs: List[Dict[str, Any]]) -> List[Dict[str, Any]]:
    """
    清洗从 Boss 直聘抓取的原始岗位数据。
    - 去除每个字段前后的空白字符。
    - 可以在此扩展更复杂的清洗逻辑，如薪资格式统一、公司规模提取等。
    """
    if not jobs:
        return []
    
    cleaned_jobs = []
    for job in jobs:
        cleaned_job = {}
        for key, value in job.items():
            if isinstance(value, str):
                cleaned_job[key] = value.strip()
            else:
                cleaned_job[key] = value
        cleaned_jobs.append(cleaned_job)
        
    print(f"原始数据已清洗，共处理 {len(cleaned_jobs)} 条岗位。")
    return cleaned_jobs
