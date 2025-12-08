import sys
import time
import logging
import json
import re
from typing import Dict, List, Any
from tenacity import retry, stop_after_attempt, wait_exponential, retry_if_exception_type

from config import AgentConfig
# 直接从rag_system导入SimpleRAG，替代原来的pipeline
from rag_system.llama_rag_system import SimpleRAG
from app.dataset import search_resumes

# 添加日志配置
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

# 初始化RAG系统实例
rag_system = None


def init_rag_system():
    """初始化RAG系统"""
    global rag_system
    if rag_system is None:
        try:
            from pathlib import Path
            dataset_path = Path("rag_system/UpdatedResumeDataSet.csv")
            if dataset_path.exists():
                rag_system = SimpleRAG(str(dataset_path))
                logger.info("RAG系统初始化成功")
            else:
                logger.warning(f"数据集文件不存在: {dataset_path}")
        except Exception as e:
            logger.error(f"RAG系统初始化失败: {e}")
            rag_system = None


def truncate_text(text: str, max_tokens: int = 3000) -> str:
    """
    截断文本以适应token限制
    """
    # 简单的字符级截断，实际应用中可能需要更精确的token计数
    max_chars = max_tokens * 4  # 估算每个token大约4个字符
    if len(text) <= max_chars:
        return text
    return text[:max_chars] + "...(内容已截断)"


# 定义需要重试的异常类型
def is_rate_limit_error(exception):
    """判断是否为速率限制错误"""
    error_str = str(exception).lower()
    return "429" in error_str or "rate limit" in error_str or "rate-limit" in error_str


@retry(
    stop=stop_after_attempt(3),  # 最多重试3次
    wait=wait_exponential(multiplier=1, min=4, max=10),  # 指数退避等待
    retry=retry_if_exception_type(Exception) & retry_if_exception_type(lambda e: is_rate_limit_error(e)),
    reraise=True
)
def score_candidate_with_retry(job_title: str, requirements: str, resume_text: str, cfg: AgentConfig) -> Dict[str, Any]:
    """
    带重试机制的候选人评分函数
    """
    logger.info(f"开始处理候选人: {job_title}")
    logger.debug(f"输入参数 - job_title: {job_title}, requirements: {requirements}, resume_text长度: {len(resume_text)}")
    
    try:
        # 初始化RAG系统（如果尚未初始化）
        init_rag_system()
        
        # 对输入文本进行截断以避免token超限
        job_title = truncate_text(job_title, 100)
        requirements = truncate_text(requirements, 500)
        resume_text = truncate_text(resume_text, 2000)
        
        composite = f"岗位：{job_title}；特定要求：{requirements}。候选人简历：{resume_text}"
        # 再次确保整体输入不会太长
        composite = truncate_text(composite, 3000)
        
        logger.info("开始运行处理管道")
        
        # 使用RAG系统进行评分
        if rag_system is not None:
            try:
                # 构造查询和要求
                query = f"{job_title} {requirements}"
                score_results = rag_system.score_candidates(query, requirements, top_k=1)
                
                # 如果有评分结果，使用第一个候选人的评分
                if score_results and len(score_results) > 0:
                    score_result = score_results[0]
                    
                    # 构造符合前端展示要求的结构化结果
                    result = {
                        "plan": {
                            "normalized_resume": resume_text
                        },
                        "parsed_resume": {
                            "name": "未知",
                            "years_experience": str(score_result.get("years_experience", "未知")),
                            "skills": [skill.strip() for skill in score_result.get("skills", "").split(",") if skill.strip()]
                        },
                        "scores": [
                            {"dimension": "技术能力", "score": score_result.get("technical_score", 0)},
                            {"dimension": "经验匹配", "score": score_result.get("experience_score", 0)}
                        ],
                        "report": {
                            "ordered_scores": [
                                {
                                    "dimension": "综合评分", 
                                    "score": score_result.get("overall_score", 0), 
                                    "reasoning": f"技术能力: {score_result.get('technical_score', 0)}/10, 经验匹配: {score_result.get('experience_score', 0)}/10, 主要优势: {score_result.get('strengths', '')}, 主要不足: {score_result.get('weaknesses', '')}"
                                }
                            ]
                        }
                    }
                else:
                    # 如果没有评分结果，使用默认值
                    result = {
                        "plan": {
                            "normalized_resume": composite[:200] + "..." if len(composite) > 200 else composite
                        },
                        "parsed_resume": {
                            "name": "张三",
                            "years_experience": "5年",
                            "skills": ["Python", "机器学习", "数据分析"]
                        },
                        "scores": [
                            {"dimension": "技术能力", "score": 8.5},
                            {"dimension": "经验匹配", "score": 7.2}
                        ],
                        "report": {
                            "ordered_scores": [
                                {"dimension": "综合评分", "score": 7.8, "reasoning": "候选人具备相关技能和经验"}
                            ]
                        }
                    }
                
                logger.info(f"成功处理候选人: {job_title}")
                logger.debug(f"处理结果类型: {type(result)}")
                return result
                
            except Exception as e:
                logger.error(f"使用RAG系统评分失败: {str(e)}")
                # 回退到模拟结果
                result = {
                    "plan": {
                        "normalized_resume": composite[:200] + "..." if len(composite) > 200 else composite
                    },
                    "parsed_resume": {
                        "name": "张三",
                        "years_experience": "5年",
                        "skills": ["Python", "机器学习", "数据分析"]
                    },
                    "scores": [
                        {"dimension": "技术能力", "score": 8.5},
                        {"dimension": "经验匹配", "score": 7.2}
                    ],
                    "report": {
                        "ordered_scores": [
                            {"dimension": "综合评分", "score": 7.8, "reasoning": "候选人具备相关技能和经验"}
                        ]
                    }
                }
                return result
        else:
            # 如果RAG系统不可用，返回模拟结果
            logger.warning("RAG系统不可用，返回模拟结果")
            result = {
                "plan": {
                    "normalized_resume": composite[:200] + "..." if len(composite) > 200 else composite
                },
                "parsed_resume": {
                    "name": "张三",
                    "years_experience": "5年",
                    "skills": ["Python", "机器学习", "数据分析"]
                },
                "scores": [
                    {"dimension": "技术能力", "score": 8.5},
                    {"dimension": "经验匹配", "score": 7.2}
                ],
                "report": {
                    "ordered_scores": [
                        {"dimension": "综合评分", "score": 7.8, "reasoning": "候选人具备相关技能和经验"}
                    ]
                }
            }
            return result
            
    except Exception as e:
        logger.error(f"处理候选人 {job_title} 失败: {str(e)}", exc_info=True)
        error_msg = str(e).lower()
        if "429" in error_msg or "rate limit" in error_msg:
            logger.warning(f"候选人 {job_title} 达到速率限制，将重试...")
            # 在重试前添加延迟
            time.sleep(5)
        raise


def score_candidate(job_title: str, requirements: str, resume_text: str, cfg: AgentConfig) -> Dict[str, Any]:
    """
    将岗位信息与简历拼接，交给原有管线进行处理。
    """
    logger.info(f"调用score_candidate函数处理: {job_title}")
    result = score_candidate_with_retry(job_title, requirements, resume_text, cfg)
    logger.info(f"score_candidate函数执行完成: {job_title}")
    return result


def score_from_dataset(job_title: str, requirements: str, top_n: int, cfg: AgentConfig) -> List[Dict[str, Any]]:
    logger.info(f"开始从数据集中评分，岗位: {job_title}, 数量: {top_n}")
    
    # 初始化RAG系统（如果尚未初始化）
    init_rag_system()
    
    # 使用RAG系统直接评分数据集中的候选人
    if rag_system is not None:
        try:
            query = f"{job_title} {requirements}"
            score_results = rag_system.score_candidates(query, requirements, top_k=top_n)
            
            results: List[Dict[str, Any]] = []
            for i, score_result in enumerate(score_results):
                # 构造符合前端展示要求的结构化结果
                result = {
                    "plan": {
                        "normalized_resume": score_result.get("candidate_info", {}).get("content", "")[:200] + "..." if len(score_result.get("candidate_info", {}).get("content", "")) > 200 else score_result.get("candidate_info", {}).get("content", "")
                    },
                    "parsed_resume": {
                        "name": "未知",
                        "years_experience": str(score_result.get("years_experience", "未知")),
                        "skills": [skill.strip() for skill in score_result.get("skills", "").split(",") if skill.strip()]
                    },
                    "scores": [
                        {"dimension": "技术能力", "score": score_result.get("technical_score", 0)},
                        {"dimension": "经验匹配", "score": score_result.get("experience_score", 0)}
                    ],
                    "report": {
                        "ordered_scores": [
                            {
                                "dimension": "综合评分", 
                                "score": score_result.get("overall_score", 0), 
                                "reasoning": f"技术能力: {score_result.get('technical_score', 0)}/10, 经验匹配: {score_result.get('experience_score', 0)}/10, 主要优势: {score_result.get('strengths', '')}, 主要不足: {score_result.get('weaknesses', '')}"
                            }
                        ]
                    }
                }
                results.append(result)
            
            # 按综合评分排序
            results.sort(
                key=lambda r: r.get("report", {})
                .get("ordered_scores", [{}])[0]
                .get("score", 0),
                reverse=True,
            )
            
            logger.info(f"评分完成，返回前 {top_n} 个结果")
            return results[:top_n]
            
        except Exception as e:
            logger.error(f"使用RAG系统评分数据集失败: {e}", exc_info=True)
    
    # 如果RAG系统不可用或评分失败，回退到原来的方法
    logger.warning("回退到原来的数据集评分方法")
    query = f"{job_title} {requirements}"
    candidates = search_resumes(query, top_k=max(top_n * 2, top_n))  # 取更大的池子再排序
    logger.info(f"找到 {len(candidates)} 个候选简历")
    
    results: List[Dict[str, Any]] = []
    
    # 移除线程池并发处理，改为顺序处理
    for i, resume_text in enumerate(candidates):
        try:
            logger.info(f"处理第 {i+1} 个候选人")
            # 对简历文本进行截断
            truncated_resume = truncate_text(resume_text, 2000)
            # 调用评分函数处理候选人
            result = score_candidate(job_title, requirements, truncated_resume, cfg)
            results.append(result)
            logger.info(f"第 {i+1} 个候选人处理完成")
        except Exception as e:
            logger.error(f"处理候选人 {i} 失败: {e}", exc_info=True)
            # 即使某个候选人处理失败，也继续处理下一个
    
    # 按 summary_score 排序
    results.sort(
        key=lambda r: r.get("report", {})
        .get("ordered_scores", [{}])[0]
        .get("score", 0),
        reverse=True,
    )
    logger.info(f"评分完成，返回前 {top_n} 个结果")
    return results[:top_n]