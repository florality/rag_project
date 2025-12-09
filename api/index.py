from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
import os
import sys
from pathlib import Path

# 添加项目根目录到Python路径
project_root = Path(__file__).parent.parent
sys.path.insert(0, str(project_root))

# 创建轻量级应用实例
app = FastAPI(title="简历筛选助手 API", version="0.1.0")

# 添加CORS中间件以允许跨域请求
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

@app.get("/")
async def root():
    return {
        "message": "简历筛选助手API",
        "status": "运行中",
        "version": "0.1.0",
        "note": "此版本为轻量级部署版本，部分AI功能可能受限"
    }

@app.get("/health")
async def health():
    return {"status": "正常"}

# 简单的演示接口
@app.post("/demo")
async def demo_endpoint():
    return {
        "message": "演示接口",
        "note": "完整功能需要在本地环境运行"
    }

# Vercel Serverless Function handler
def handler(request, context):
    """Vercel Serverless Function入口点"""
    # 使用ASGI适配器
    from asgiref.wsgi import WsgiToAsgi
    asgi_app = WsgiToAsgi(app)
    return asgi_app(request.scope, request.receive, request.send)

if __name__ == "__main__":
    import uvicorn
    port = int(os.environ.get("PORT", 8000))
    uvicorn.run(app, host="0.0.0.0", port=port)