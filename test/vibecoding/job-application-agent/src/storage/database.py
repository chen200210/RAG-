import sqlite3
from typing import List, Dict, Any, Optional, Sequence

def fetch_jobs_from_db(db_path: str, table: str = "job_info", limit: Optional[int] = None) -> List[Dict[str, Any]]:
    """
    从指定的 SQLite 数据库文件中获取所有岗位信息。

    Args:
        db_path (str): SQLite 数据库文件的路径。

    Returns:
        List[Dict[str, Any]]: 一个包含所有岗位信息的字典列表。
    """
    jobs: List[Dict[str, Any]] = []
    try:
        conn = sqlite3.connect(db_path)
        conn.row_factory = sqlite3.Row
        cursor = conn.cursor()

        sql = f"SELECT * FROM {table}"
        params: Sequence[object] = ()
        if limit is not None:
            sql += " LIMIT ?"
            params = (limit,)

        cursor.execute(sql, params)
        rows = cursor.fetchall()
        
        for row in rows:
            jobs.append(dict(row))
            
        conn.close()
        print(f"成功从 '{db_path}' 读取了 {len(jobs)} 条岗位信息。")
        return jobs
    except sqlite3.Error as e:
        print(f"读取数据库 '{db_path}' 失败: {e}")
        return []
