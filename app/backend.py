import json
from pathlib import Path
from typing import List, Any

import uvicorn
from fastapi import FastAPI, HTTPException
from pydantic import BaseModel, Field
from dotenv import load_dotenv

from config import get_config
from app.service import score_candidate, score_from_dataset  # 更新导入
from app.port_utils import find_free_port

class ScoreRequest(BaseModel):
    job_title: str = Field(..., description="岗位名称")
    requirements: str = Field("", description="特定要求/偏好")
    top_n: int = Field(3, description="返回前 N 个候选人")


class ScoreItem(BaseModel):
    resume_index: int
    original_id: int  # 新增：原始数据集中的ID
    rerank_score: float  # 新增：重排序分数
    plan: dict
    parsed_resume: dict
    scores: list
    report: dict
    summary_score: float
    raw_resume: str


class ScoreResponse(BaseModel):
    results: List[ScoreItem]


def _write_port_file(port: int):
    Path("backend_port.txt").write_text(str(port), encoding="utf-8")


def create_app() -> FastAPI:
    load_dotenv()
    cfg = get_config()
    app = FastAPI(title="简历筛选助手 API", version="0.1.0")  # 修改标题为中文

    @app.get("/health")
    def health():
        return {"status": "正常"}  # 修改为中文

    # 修改为同步端点
    @app.post("/score", response_model=ScoreResponse)
    def score(req: ScoreRequest):
        if not cfg.api_key:
            raise HTTPException(status_code=400, detail="缺少API密钥。")
        try:
            # 使用同步函数处理评分
            ranked = score_from_dataset(req.job_title, req.requirements, req.top_n, cfg)
        except Exception as exc:  # noqa: BLE001
            raise HTTPException(status_code=500, detail=f"搜索/评分失败: {exc}") from exc

        items: List[ScoreItem] = []
        for idx, result in enumerate(ranked):
            summary_score = result["report"]["ordered_scores"][0]["score"] if result["report"]["ordered_scores"] else 0
            raw_resume = result.get("plan", {}).get("normalized_resume", "")
            
            # 获取原始ID和重排序分数
            original_id = result.get("candidate_info", {}).get("id", idx)
            rerank_score = result.get("candidate_info", {}).get("rerank_score", 0.0)
            
            items.append(
                ScoreItem(
                    resume_index=idx,
                    original_id=original_id,  # 添加原始ID
                    rerank_score=rerank_score,  # 添加重排序分数
                    plan=result["plan"],
                    parsed_resume=result["parsed_resume"],
                    scores=result["scores"],
                    report=result["report"],
                    summary_score=summary_score,
                    raw_resume=raw_resume,
                )
            )
        return ScoreResponse(results=items)

    return app


def run():
    app = create_app()
    # port_start = (
    #     int(Path("backend_port.txt").read_text().strip())
    #     if Path("backend_port.txt").exists()
    #     else 8080
    # )
    # port = find_free_port(port_start)
    # _write_port_file(port)
    # print(f"[后端] 运行在 http://127.0.0.1:{port}")  # 修改为中文
    # # 使用同步服务器运行
    # uvicorn.run(app, host="0.0.0.0", port=port, log_level="info")


    # 优先使用 Render 的环境变量 PORT
    port = int(os.environ.get("PORT", 8000))
    
    # 如果 Render 没有提供 PORT，则使用备用端口发现机制
    if port == 8000:  # 说明是默认值，Render 没有提供 PORT
        port_start = (
            int(Path("backend_port.txt").read_text().strip())
            if Path("backend_port.txt").exists()
            else 8080
        )
        port = find_free_port(port_start)
        _write_port_file(port)
    
    # 修正：绑定到 0.0.0.0 而不是 127.0.0.1
    host = "0.0.0.0"
    
    print(f"[后端] 运行在 http://{host}:{port}")  # 修正显示信息
    
    # 使用同步服务器运行
    uvicorn.run(
        app, 
        host=host,  # 关键修改：使用 0.0.0.0
        port=port, 
        log_level="info"
    )


if __name__ == "__main__":
    run()
