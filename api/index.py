from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
import gradio as gr
import os
import sys
from pathlib import Path

# 添加项目根目录到Python路径
project_root = Path(__file__).parent.parent
sys.path.insert(0, str(project_root))

# 导入现有的应用组件
from app.backend import create_app

# 创建应用实例
app = create_app()

# 添加CORS中间件以允许跨域请求
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# 创建Gradio界面
try:
    from app.frontend import build_demo
    demo = build_demo()
    # 将Gradio界面挂载为FastAPI的一个路由
    app = gr.mount_gradio_app(app, demo, path="/")
except Exception as e:
    print(f"Warning: Could not mount Gradio app: {e}")

@app.get("/")
async def root():
    return {"message": "简历筛选助手API"}

# Vercel Serverless Function handler - 修正参数格式
def handler(request, context):
    """Vercel Serverless Function入口点"""
    # 将Vercel请求转换为ASGI请求
    from asgiref.wsgi import WsgiToAsgi
    asgi_app = WsgiToAsgi(app)
    return asgi_app(request.scope, request.receive, request.send)

if __name__ == "__main__":
    import uvicorn
    port = int(os.environ.get("PORT", 8000))
    uvicorn.run(app, host="0.0.0.0", port=port)