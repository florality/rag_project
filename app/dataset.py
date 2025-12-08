import csv
import re
from functools import lru_cache
from pathlib import Path
from typing import List, Tuple
import sys
import os

# 添加rag_system目录到Python路径
sys.path.append(os.path.join(os.path.dirname(__file__), '..', 'rag_system'))

# 修复导入路径
from rag_system.llama_rag_system import SimpleRAG

# 使用项目中的CSV文件
DATASET_PATH = Path("rag_system/UpdatedResumeDataSet.csv")

# 初始化RAG系统
rag_system = None

def init_rag_system():
    """初始化RAG系统"""
    global rag_system
    if rag_system is None and SimpleRAG is not None:
        try:
            if DATASET_PATH.exists():
                rag_system = SimpleRAG(str(DATASET_PATH))
                print("RAG系统初始化成功")
            else:
                print(f"警告: 数据集文件不存在 {DATASET_PATH}")
        except Exception as e:
            print(f"RAG系统初始化失败: {e}")
            rag_system = None

@lru_cache(maxsize=1)
def load_dataset() -> List[Tuple[str, str]]:
    """
    Load dataset as list of (category, resume_text).
    Cached to avoid re-reading.
    """
    if not DATASET_PATH.exists():
        return []
    rows: List[Tuple[str, str]] = []
    with DATASET_PATH.open("r", encoding="utf-8") as f:
        reader = csv.DictReader(f)
        for row in reader:
            cat = (row.get("Category") or "").strip()
            res = (row.get("Resume") or "").strip()
            if res:
                rows.append((cat, res))
    return rows


def _tokenize(text: str) -> List[str]:
    return re.findall(r"[a-zA-Z0-9]+", text.lower())


def search_resumes(query: str, top_k: int = 5) -> List[str]:
    """
    使用RAG系统搜索简历
    """
    # 初始化RAG系统（如果尚未初始化）
    init_rag_system()
    
    # 如果RAG系统可用，使用它进行搜索
    if rag_system is not None:
        try:
            results = rag_system.search(query, top_k=top_k)
            # 提取简历内容
            return [result['content'] for result in results]
        except Exception as e:
            print(f"RAG搜索失败，回退到关键词匹配: {e}")
    
    # 回退到原来的关键词匹配方法
    corpus = load_dataset()
    if not corpus:
        return []
    query_tokens = set(_tokenize(query))
    scored: List[Tuple[float, str]] = []
    for _, resume in corpus:
        text_tokens = _tokenize(resume)
        if not text_tokens:
            continue
        overlap = len(query_tokens.intersection(text_tokens))
        if overlap > 0:
            scored.append((overlap, resume))
    scored.sort(key=lambda x: x[0], reverse=True)
    return [r for _, r in scored[:top_k]]